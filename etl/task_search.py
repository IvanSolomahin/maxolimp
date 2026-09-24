#!/usr/bin/env python3
"""Incremental hybrid search in the same SQLite database as the problems."""

import argparse
import hashlib
import json
import math
import os
import random
import re
import sqlite3
import sys
import threading
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

import requests

from parser_sdamgia_v2 import DB_FILE

DEFAULT_MODEL = "qwen/qwen3-embedding-4b"
DEFAULT_DIMENSIONS = 2560
DEFAULT_MAX_TOKENS = 32768
DEFAULT_TOKENIZER_URL = (
    "https://huggingface.co/Qwen/Qwen3-Embedding-4B/resolve/main/tokenizer.json"
)
DEFAULT_INDEX_DIR = (
    Path(__file__).resolve().parent / "olimpiads_data_v2" / "search_indexes"
)
API_URL = "https://openrouter.ai/api/v1/embeddings"
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 520, 522, 524, 529}
MAX_API_ATTEMPTS = 8


def index_path(index_dir, model, dimensions):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")[:60]
    digest = hashlib.sha256(model.encode()).hexdigest()[:12]
    return Path(index_dir) / f"{slug}-{digest}-{dimensions}.sqlite3"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def topic_text(row):
    return "\n".join(
        part for part in (row["classifier"].strip(), row["statement"].strip()) if part
    )


def get_tokenizer(path, url=None):
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Установите зависимости: pip install -r requirements.txt"
        ) from exc
    path = Path(path)
    if not path.exists():
        if not url:
            raise ValueError("Для новой модели укажите --tokenizer или --tokenizer-url")
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(response.content)
        temporary.replace(path)
    return Tokenizer.from_file(str(path))


@dataclass
class Config:
    db: Path = DB_FILE
    index_dir: Path = DEFAULT_INDEX_DIR
    model: str = DEFAULT_MODEL
    dimensions: int = DEFAULT_DIMENSIONS
    max_tokens: int = DEFAULT_MAX_TOKENS
    tokenizer: Path | None = None
    tokenizer_url: str | None = None
    api_key: str | None = None

    def tokenizer_path(self):
        if self.tokenizer:
            return Path(self.tokenizer)
        if self.model != DEFAULT_MODEL and not self.tokenizer_url:
            raise ValueError(
                "Для другой модели укажите --tokenizer или --tokenizer-url"
            )
        if self.model != DEFAULT_MODEL:
            return (
                Path(self.index_dir)
                / f"tokenizer-{hashlib.sha256(self.model.encode()).hexdigest()[:12]}.json"
            )
        return Path(self.index_dir) / "qwen3-embedding-4b-tokenizer.json"

    def tokenizer_source(self):
        return self.tokenizer_url or (
            DEFAULT_TOKENIZER_URL if self.model == DEFAULT_MODEL else None
        )


def open_index(config, writable=True):
    path = Path(config.db).resolve()
    connection = sqlite3.connect(
        path if writable else f"file:{path}?mode=ro", uri=not writable
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    if not writable:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='search_vectors'"
        ).fetchone():
            connection.close()
            raise RuntimeError(
                "Поисковые таблицы отсутствуют: выполните index или migrate"
            )
        return connection
    connection.execute("PRAGMA journal_mode=WAL")
    fts_exists = (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='problem_fts'"
        ).fetchone()
        is not None
    )
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS search_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO search_meta(key,value) VALUES ('schema_version','1');
        CREATE VIRTUAL TABLE IF NOT EXISTS problem_fts USING fts5(
            subject UNINDEXED, problem_id UNINDEXED,
            classifier, statement, solution,
            content='problems', content_rowid='rowid', tokenize='unicode61'
        );
        CREATE TRIGGER IF NOT EXISTS search_fts_ai AFTER INSERT ON problems BEGIN
            INSERT INTO problem_fts(rowid,subject,problem_id,classifier,statement,solution)
            VALUES (new.rowid,new.subject,new.problem_id,new.classifier,new.statement,new.solution);
        END;
        CREATE TRIGGER IF NOT EXISTS search_fts_ad AFTER DELETE ON problems BEGIN
            INSERT INTO problem_fts(problem_fts,rowid,subject,problem_id,classifier,statement,solution)
            VALUES ('delete',old.rowid,old.subject,old.problem_id,old.classifier,old.statement,old.solution);
        END;
        CREATE TRIGGER IF NOT EXISTS search_fts_au
        AFTER UPDATE OF subject,problem_id,classifier,statement,solution ON problems BEGIN
            INSERT INTO problem_fts(problem_fts,rowid,subject,problem_id,classifier,statement,solution)
            VALUES ('delete',old.rowid,old.subject,old.problem_id,old.classifier,old.statement,old.solution);
            INSERT INTO problem_fts(rowid,subject,problem_id,classifier,statement,solution)
            VALUES (new.rowid,new.subject,new.problem_id,new.classifier,new.statement,new.solution);
        END;
        CREATE TABLE IF NOT EXISTS search_vectors (
            model TEXT NOT NULL, dimensions INTEGER NOT NULL,
            subject TEXT NOT NULL, problem_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('topic', 'solution')),
            text_hash TEXT NOT NULL, vector BLOB NOT NULL,
            PRIMARY KEY(model, dimensions, subject, problem_id, kind),
            FOREIGN KEY(subject,problem_id) REFERENCES problems(subject,problem_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_search_vectors_lookup
            ON search_vectors(model,dimensions,kind,subject,problem_id);
        CREATE TABLE IF NOT EXISTS search_skipped (
            model TEXT NOT NULL, dimensions INTEGER NOT NULL,
            subject TEXT NOT NULL, problem_id INTEGER NOT NULL,
            kind TEXT NOT NULL, text_hash TEXT NOT NULL,
            tokens INTEGER NOT NULL, reason TEXT NOT NULL,
            PRIMARY KEY(model,dimensions,subject,problem_id,kind),
            FOREIGN KEY(subject,problem_id) REFERENCES problems(subject,problem_id) ON DELETE CASCADE
        );
    """)
    version = connection.execute(
        "SELECT value FROM search_meta WHERE key='schema_version'"
    ).fetchone()[0]
    if version != "1":
        connection.close()
        raise RuntimeError(f"Неизвестная версия поисковой схемы: {version}")
    if not fts_exists:
        connection.execute("INSERT INTO problem_fts(problem_fts) VALUES ('rebuild')")
    connection.commit()
    return connection


class RequestGate:
    """Ramp API concurrency up slowly and lower it after transient failures."""

    def __init__(self, workers):
        self.maximum = workers
        self.limit = min(workers, 8)
        self.active = 0
        self.successes = 0
        self.retries = 0
        self.condition = threading.Condition()

    def acquire(self):
        with self.condition:
            while self.active >= self.limit:
                self.condition.wait()
            self.active += 1

    def release(self, outcome):
        with self.condition:
            self.active -= 1
            if outcome == "retry":
                self.retries += 1
                self.limit = max(1, self.limit // 2)
                self.successes = 0
            elif outcome == "success" and self.limit < self.maximum:
                self.successes += 1
                if self.successes >= self.limit * 4:
                    self.limit += 1
                    self.successes = 0
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return self.active, self.limit, self.retries


def embed(texts, config, session=None, gate=None):
    """Return vectors in input order and token usage. Validate the whole response."""
    if not texts:
        return [], 0
    key = config.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Нужен OPENROUTER_API_KEY")
    own_session = session is None
    session = session or requests.Session()
    payload = {"model": config.model, "input": texts}
    if config.dimensions != DEFAULT_DIMENSIONS or config.model != DEFAULT_MODEL:
        payload["dimensions"] = config.dimensions
    try:
        for attempt in range(MAX_API_ATTEMPTS):
            if gate:
                gate.acquire()
            try:
                response = session.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                    timeout=120,
                )
            except requests.RequestException:
                if gate:
                    gate.release("retry")
                if attempt == MAX_API_ATTEMPTS - 1:
                    raise
                time.sleep(min(30, 2**attempt) + random.uniform(0, 1))
                continue
            if response.status_code in RETRYABLE_STATUS:
                if gate:
                    gate.release("retry")
                if attempt == MAX_API_ATTEMPTS - 1:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After", "")
                delay = (
                    float(retry_after)
                    if retry_after.replace(".", "", 1).isdigit()
                    else 2**attempt
                )
                time.sleep(min(60, delay) + random.uniform(0, 1))
                continue
            if gate:
                gate.release("success" if response.status_code < 400 else None)
            response.raise_for_status()
            body = response.json()
            break
    finally:
        if own_session:
            session.close()
    data = body.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise ValueError("OpenRouter вернул неверное число векторов")
    vectors = [None] * len(texts)
    for item in data:
        position = item.get("index")
        vector = item.get("embedding")
        if (
            not isinstance(position, int)
            or not 0 <= position < len(texts)
            or vectors[position] is not None
        ):
            raise ValueError("OpenRouter вернул неверные индексы векторов")
        if (
            not isinstance(vector, list)
            or len(vector) != config.dimensions
            or not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in vector
            )
        ):
            raise ValueError(
                "OpenRouter вернул неверную размерность или значения вектора"
            )
        vectors[position] = vector
    return vectors, (body.get("usage") or {}).get("total_tokens", 0)


def _source(config):
    uri = f"file:{Path(config.db).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _pending_kinds(index, config, row):
    subject, problem_id = row["subject"], row["problem_id"]
    work = []
    for kind, content in (
        ("topic", topic_text(row)),
        ("solution", row["solution"].strip()),
    ):
        key = (config.model, config.dimensions, subject, problem_id, kind)
        vector = index.execute(
            """SELECT text_hash FROM search_vectors
            WHERE model=? AND dimensions=? AND subject=? AND problem_id=? AND kind=?""",
            key,
        ).fetchone()
        skipped = index.execute(
            """SELECT text_hash FROM search_skipped
            WHERE model=? AND dimensions=? AND subject=? AND problem_id=? AND kind=?""",
            key,
        ).fetchone()
        hash_value = digest(content)
        if not content:
            if vector or skipped:
                work.append((kind, content, hash_value))
        elif not (
            (vector and vector["text_hash"] == hash_value and not skipped)
            or (not vector and skipped and skipped["text_hash"] == hash_value)
        ):
            work.append((kind, content, hash_value))
    return work


def build_index(
    config=Config(),
    limit=None,
    batch_size=32,
    session=None,
    workers=1,
    subject=None,
    progress=None,
):
    """Update the index. A limit is for pilot runs and suppresses deletion of unseen rows."""
    if batch_size < 1 or workers < 1 or (limit is not None and limit < 1):
        raise ValueError("batch_size, workers и limit должны быть положительными")
    if subject not in (None, "math", "physics"):
        raise ValueError("Предмет: math или physics")
    tokenizer = get_tokenizer(config.tokenizer_path(), config.tokenizer_source())
    import numpy as np

    start = time.monotonic()
    report = {
        "scanned": 0,
        "embedded": 0,
        "unchanged": 0,
        "skipped": [],
        "deleted": 0,
        "tokens": 0,
    }
    index, source = open_index(config), _source(config)
    pending = []
    inflight = deque()
    pool = ThreadPoolExecutor(max_workers=workers)
    gate = RequestGate(workers)
    total_query = "SELECT count(*) FROM problems WHERE (trim(statement)!='' OR trim(classifier)!='' OR trim(solution)!='')"
    if subject:
        total_query += " AND subject=?"
    source_total = source.execute(
        total_query, (subject,) if subject else ()
    ).fetchone()[0]
    if limit is not None:
        source_total = min(source_total, limit)

    def update_progress(final=False):
        if progress:
            active, concurrency, retries = gate.snapshot()
            progress(
                {
                    "scanned": report["scanned"],
                    "total": source_total,
                    "embedded": report["embedded"],
                    "tokens": report["tokens"],
                    "skipped": len(report["skipped"]),
                    "inflight": len(inflight),
                    "api_active": active,
                    "api_limit": concurrency,
                    "retries": retries,
                    "seconds": time.monotonic() - start,
                    "final": final,
                }
            )

    def finish_one():
        done, _ = wait([future for _, future in inflight], return_when=FIRST_COMPLETED)
        items, future = next(pair for pair in inflight if pair[1] in done)
        inflight.remove((items, future))
        vectors, used = future.result()
        report["tokens"] += used
        for (subj, problem_id, kind, _, hash_value), vector in zip(items, vectors):
            blob = np.asarray(vector, dtype="<f4").tobytes()
            index.execute(
                """INSERT INTO search_vectors VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(model,dimensions,subject,problem_id,kind)
                DO UPDATE SET text_hash=excluded.text_hash, vector=excluded.vector""",
                (
                    config.model,
                    config.dimensions,
                    subj,
                    problem_id,
                    kind,
                    hash_value,
                    blob,
                ),
            )
            index.execute(
                """DELETE FROM search_skipped
                WHERE model=? AND dimensions=? AND subject=? AND problem_id=? AND kind=?""",
                (config.model, config.dimensions, subj, problem_id, kind),
            )
            report["embedded"] += 1
        index.commit()
        update_progress()

    def flush():
        if not pending:
            return
        items = pending.copy()
        future = pool.submit(embed, [item[3] for item in items], config, session, gate)
        inflight.append((items, future))
        pending.clear()
        if len(inflight) >= workers:
            finish_one()

    try:
        update_progress()
        sql = "SELECT subject,problem_id,grade,year,url,statement,classifier,solution FROM problems WHERE (trim(statement)!='' OR trim(classifier)!='' OR trim(solution)!='')"
        if subject:
            sql += " AND subject=?"
        sql += " ORDER BY subject,problem_id"
        source_rows = source.execute(sql, (subject,) if subject else ())
        for row in source_rows:
            if limit is not None and report["scanned"] >= limit:
                break
            report["scanned"] += 1
            changes = _pending_kinds(index, config, row)
            report["unchanged"] += 2 - len(changes)
            for kind, content, hash_value in changes:
                key = (
                    config.model,
                    config.dimensions,
                    row["subject"],
                    row["problem_id"],
                    kind,
                )
                index.execute(
                    """DELETE FROM search_vectors
                    WHERE model=? AND dimensions=? AND subject=? AND problem_id=? AND kind=?""",
                    key,
                )
                index.execute(
                    """DELETE FROM search_skipped
                    WHERE model=? AND dimensions=? AND subject=? AND problem_id=? AND kind=?""",
                    key,
                )
                if not content:
                    continue
                count = len(tokenizer.encode(content).ids)
                if count > config.max_tokens:
                    item = {
                        "subject": row["subject"],
                        "problem_id": row["problem_id"],
                        "kind": kind,
                        "tokens": count,
                    }
                    report["skipped"].append(item)
                    index.execute(
                        "INSERT INTO search_skipped VALUES (?,?,?,?,?,?,?,?)",
                        (*key, hash_value, count, "too_long"),
                    )
                    continue
                pending.append(
                    (row["subject"], row["problem_id"], kind, content, hash_value)
                )
                if len(pending) >= batch_size:
                    flush()
            if report["scanned"] % 100 == 0:
                index.commit()
                update_progress()
        flush()
        while inflight:
            finish_one()
        if limit is None and subject is None:
            stale = index.execute(
                """WITH indexed AS (
                SELECT subject,problem_id FROM search_vectors WHERE model=? AND dimensions=?
                UNION SELECT subject,problem_id FROM search_skipped WHERE model=? AND dimensions=?
            ) SELECT v.subject,v.problem_id FROM indexed v WHERE NOT EXISTS (
                SELECT 1 FROM problems p WHERE p.subject=v.subject AND p.problem_id=v.problem_id
                AND (trim(p.statement)!='' OR trim(p.classifier)!='' OR trim(p.solution)!='')
            )""",
                (config.model, config.dimensions, config.model, config.dimensions),
            ).fetchall()
            for row in stale:
                key = (
                    config.model,
                    config.dimensions,
                    row["subject"],
                    row["problem_id"],
                )
                for table in ("search_vectors", "search_skipped"):
                    index.execute(
                        f"""DELETE FROM {table} WHERE model=? AND dimensions=?
                        AND subject=? AND problem_id=?""",
                        key,
                    )
            report["deleted"] = len(stale)
        index.commit()
        report["skipped"] = [
            dict(row)
            for row in index.execute(
                """SELECT subject,problem_id,kind,tokens
            FROM search_skipped WHERE model=? AND dimensions=? ORDER BY subject,problem_id,kind""",
                (config.model, config.dimensions),
            )
        ]
        report["seconds"] = round(time.monotonic() - start, 2)
        update_progress(final=True)
        return report
    finally:
        pool.shutdown(wait=True)
        source.close()
        index.close()


def migrate_legacy_index(config=Config(), legacy_path=None):
    """Copy the existing separate index into the source DB without API calls."""
    legacy_path = Path(
        legacy_path or index_path(config.index_dir, config.model, config.dimensions)
    ).resolve()
    if not legacy_path.is_file() or legacy_path == Path(config.db).resolve():
        raise ValueError(f"Не найден отдельный индекс: {legacy_path}")
    legacy = sqlite3.connect(f"file:{legacy_path}?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    index = open_index(config)
    try:
        count = 0
        for item in legacy.execute(
            "SELECT subject,problem_id,kind,text_hash,length(vector) AS bytes FROM vectors"
        ):
            row = index.execute(
                """SELECT classifier,statement,solution FROM problems
                WHERE subject=? AND problem_id=?""",
                (item["subject"], item["problem_id"]),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"Нет исходной задачи: {item['subject']}/{item['problem_id']}"
                )
            content = (
                topic_text(row) if item["kind"] == "topic" else row["solution"].strip()
            )
            if (
                not content
                or digest(content) != item["text_hash"]
                or item["bytes"] != config.dimensions * 4
            ):
                raise ValueError(
                    f"Исходный текст или размерность изменились: {item['subject']}/{item['problem_id']}/{item['kind']}"
                )
            count += 1
        index.execute("ATTACH DATABASE ? AS legacy_search", (str(legacy_path),))
        index.execute(
            """INSERT OR REPLACE INTO search_vectors
            (model,dimensions,subject,problem_id,kind,text_hash,vector)
            SELECT ?,?,subject,problem_id,kind,text_hash,vector FROM legacy_search.vectors""",
            (config.model, config.dimensions),
        )
        index.execute(
            """INSERT OR REPLACE INTO search_skipped
            (model,dimensions,subject,problem_id,kind,text_hash,tokens,reason)
            SELECT ?,?,subject,problem_id,kind,text_hash,tokens,reason FROM legacy_search.skipped""",
            (config.model, config.dimensions),
        )
        index.commit()
        stored = index.execute(
            """SELECT count(*) FROM search_vectors
            WHERE model=? AND dimensions=?""",
            (config.model, config.dimensions),
        ).fetchone()[0]
        if stored != count:
            raise RuntimeError(f"Перенесено {stored} из {count} векторов")
        return {
            "model": config.model,
            "dimensions": config.dimensions,
            "vectors": stored,
            "problems": index.execute("SELECT count(*) FROM problems").fetchone()[0],
        }
    finally:
        legacy.close()
        index.close()


def _filters(alias, subject, grade, year):
    clauses, parameters = [], []
    for name, value in (("subject", subject), ("year", year)):
        if value is not None:
            clauses.append(f"{alias}.{name}=?")
            parameters.append(str(value))
    if grade is not None:
        clauses.append(
            f"({alias}.grade=? OR (instr({alias}.grade,'-')>0 AND CAST(substr({alias}.grade,1,instr({alias}.grade,'-')-1) AS INTEGER)<=? AND CAST(substr({alias}.grade,instr({alias}.grade,'-')+1) AS INTEGER)>=?))"
        )
        parameters.extend((str(grade), int(grade), int(grade)))
    return (" AND ".join(clauses) if clauses else "1=1"), parameters


def search(
    query,
    mode="both",
    k=10,
    subject=None,
    grade=None,
    year=None,
    method="hybrid",
    config=Config(),
    session=None,
):
    """Return ranked problems. mode: topic, solution, both; method: hybrid, vector, fts."""
    if not query.strip() or k < 1:
        raise ValueError("Нужны непустой запрос и положительное число результатов")
    if mode not in ("topic", "solution", "both") or method not in (
        "hybrid",
        "vector",
        "fts",
    ):
        raise ValueError("Неизвестный режим поиска")
    if subject not in (None, "math", "physics"):
        raise ValueError("Предмет: math или physics")
    import numpy as np

    index = open_index(config, writable=False)
    try:
        if (
            method in ("vector", "hybrid")
            and not index.execute(
                """SELECT 1 FROM search_vectors
            WHERE model=? AND dimensions=? LIMIT 1""",
                (config.model, config.dimensions),
            ).fetchone()
        ):
            raise RuntimeError(
                "Для этой модели нет векторов: сначала выполните index или migrate"
            )
        scores = {}
        where, params = _filters("d", subject, grade, year)
        if method in ("fts", "hybrid"):
            terms = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
            if terms:
                fields = (
                    ("classifier", "statement", "solution")
                    if mode == "both"
                    else (
                        ("classifier", "statement")
                        if mode == "topic"
                        else ("solution",)
                    )
                )
                expression = " OR ".join(
                    f'{field}:"{term}"' for field in fields for term in terms
                )
                rows = index.execute(
                    f"""SELECT d.subject,d.problem_id,bm25(problem_fts) AS score
                    FROM problem_fts JOIN problems d ON d.rowid=problem_fts.rowid
                    WHERE problem_fts MATCH ? AND {where} ORDER BY score LIMIT ?""",
                    (expression, *params, max(k * 20, 200)),
                ).fetchall()
                for rank, row in enumerate(rows, 1):
                    scores.setdefault((row["subject"], row["problem_id"]), {})[
                        "fts"
                    ] = rank
        if method in ("vector", "hybrid"):
            tokenizer = get_tokenizer(
                config.tokenizer_path(), config.tokenizer_source()
            )
            if len(tokenizer.encode(query).ids) > config.max_tokens:
                raise ValueError("Запрос превышает лимит токенов модели")
            qvector = np.asarray(embed([query], config, session)[0][0], dtype="<f4")
            qnorm = np.linalg.norm(qvector)
            kinds = ("topic", "solution") if mode == "both" else (mode,)
            for kind in kinds:
                rows = index.execute(
                    f"""SELECT v.subject,v.problem_id,v.vector FROM search_vectors v
                    JOIN problems d ON d.subject=v.subject AND d.problem_id=v.problem_id
                    WHERE v.model=? AND v.dimensions=? AND v.kind=? AND {where}""",
                    (config.model, config.dimensions, kind, *params),
                )
                similarities = []
                for row in rows:
                    vector = np.frombuffer(row["vector"], dtype="<f4")
                    if len(vector) != config.dimensions:
                        raise ValueError("В индексе вектор неверной размерности")
                    norm = np.linalg.norm(vector) * qnorm
                    similarity = float(np.dot(vector, qvector) / norm) if norm else 0.0
                    similarities.append((similarity, row["subject"], row["problem_id"]))
                similarities.sort(reverse=True)
                for rank, (_, subj, problem_id) in enumerate(
                    similarities[: max(k * 20, 200)], 1
                ):
                    scores.setdefault((subj, problem_id), {})[kind] = rank
        ranked = sorted(
            scores,
            key=lambda key: (
                -sum(1 / (60 + rank) for rank in scores[key].values()),
                key,
            ),
        )
        results, seen = [], {}
        for subj, problem_id in ranked:
            row = index.execute(
                "SELECT * FROM problems WHERE subject=? AND problem_id=?",
                (subj, problem_id),
            ).fetchone()
            if not row:
                continue
            duplicate_key = (
                subj,
                digest(row["statement"].strip())
                if row["statement"].strip()
                else f"id:{problem_id}",
            )
            if duplicate_key in seen:
                seen[duplicate_key]["duplicates"].append(problem_id)
                continue
            item = {
                field: row[field]
                for field in (
                    "subject",
                    "problem_id",
                    "grade",
                    "year",
                    "url",
                    "statement",
                    "classifier",
                    "solution",
                )
            }
            item["score"] = round(
                sum(1 / (60 + rank) for rank in scores[(subj, problem_id)].values()), 6
            )
            item["duplicates"] = []
            seen[duplicate_key] = item
            results.append(item)
            if len(results) >= k:
                break
        for item in results:
            if item["statement"].strip():
                duplicate_where, duplicate_params = _filters("d", subject, grade, year)
                item["duplicates"] = [
                    row[0]
                    for row in index.execute(
                        f"SELECT d.problem_id FROM problems d WHERE d.subject=? AND trim(d.statement)=? AND d.problem_id!=? AND {duplicate_where} ORDER BY d.problem_id",
                        (
                            item["subject"],
                            item["statement"].strip(),
                            item["problem_id"],
                            *duplicate_params,
                        ),
                    )
                ]
        return results
    finally:
        index.close()


class ProgressPrinter:
    """A terminal bar, or periodic lines when output is redirected."""

    def __init__(self):
        self.terminal = sys.stderr.isatty()
        self.last_print = 0.0
        self.samples = deque()

    def __call__(self, state):
        now = time.monotonic()
        if not state["final"] and now - self.last_print < (
            0.25 if self.terminal else 5
        ):
            return
        self.last_print = now
        total = state["total"]
        fraction = state["scanned"] / total if total else 1.0
        elapsed = state["seconds"]
        self.samples.append((elapsed, state["scanned"]))
        while len(self.samples) > 1 and elapsed - self.samples[0][0] > 30:
            self.samples.popleft()
        if state["final"]:
            remaining = "готово"
        elif fraction >= 1:
            remaining = f"ожидание {state['inflight']} пакетов"
        elif fraction > 0:
            eta = elapsed * (1 - fraction) / fraction
            old_elapsed, old_scanned = self.samples[0]
            recent_seconds = elapsed - old_elapsed
            recent_tasks = state["scanned"] - old_scanned
            if recent_seconds >= 5 and recent_tasks > 0:
                recent_eta = (total - state["scanned"]) * recent_seconds / recent_tasks
                eta = max(eta, recent_eta)
            remaining = f"≈{self._duration(eta)} осталось"
        else:
            remaining = "оценка времени после первых задач"
        prefix = ""
        if self.terminal:
            filled = round(24 * fraction)
            prefix = "[" + "#" * filled + "." * (24 - filled) + "] "
        line = (
            f"{prefix}{state['scanned']}/{total} задач ({fraction:.1%}) | "
            f"+{state['embedded']} векторов | {state['tokens']:,} токенов | "
            f"API {state['api_active']} (лимит {state['api_limit']}, повторы {state['retries']}) | "
            f"{self._duration(elapsed)} прошло | {remaining}"
        )
        print(
            ("\r" if self.terminal else "") + line,
            end="\n" if state["final"] or not self.terminal else "",
            file=sys.stderr,
            flush=True,
        )

    @staticmethod
    def _duration(seconds):
        seconds = max(0, round(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Гибридный поиск по олимпиадным задачам"
    )
    parser.add_argument("--db", type=Path, default=DB_FILE)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--tokenizer-url")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        help="Файл с ключом OpenRouter вместо переменной окружения",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("index", help="Создать или обновить индекс")
    build.add_argument("--limit", type=int, help="Число задач для пробного запуска")
    build.add_argument("--batch-size", type=int, default=32)
    build.add_argument("--workers", type=int, default=1)
    build.add_argument(
        "--subject",
        choices=("math", "physics"),
        help="Индексировать только один предмет",
    )
    build.add_argument(
        "--price-per-million",
        type=float,
        help="Цена модели в USD за миллион входных токенов",
    )
    build.add_argument(
        "--no-progress", action="store_true", help="Скрыть ход индексирования"
    )
    find = commands.add_parser("search", help="Искать задачи")
    find.add_argument("query")
    find.add_argument("--mode", choices=("topic", "solution", "both"), default="both")
    find.add_argument("--method", choices=("hybrid", "vector", "fts"), default="hybrid")
    find.add_argument("-k", type=int, default=10)
    find.add_argument("--subject", choices=("math", "physics"))
    find.add_argument("--grade")
    find.add_argument("--year")
    migrate = commands.add_parser(
        "migrate", help="Перенести отдельный индекс в исходную БД без API"
    )
    migrate.add_argument(
        "--legacy-index", type=Path, help="Путь к прежнему отдельному индексу"
    )
    args = parser.parse_args()
    key = (
        args.api_key_file.read_text(encoding="utf-8").strip()
        if args.api_key_file
        else None
    )
    config = Config(
        args.db,
        args.index_dir,
        args.model,
        args.dimensions,
        args.max_tokens,
        args.tokenizer,
        args.tokenizer_url,
        key,
    )
    if config.dimensions < 1 or config.max_tokens < 1:
        parser.error("dimensions и max-tokens должны быть положительными")
    try:
        if args.command == "index":
            if args.price_per_million is not None and args.price_per_million < 0:
                raise ValueError("Цена должна быть неотрицательной")
            reporter = None if args.no_progress else ProgressPrinter()
            result = build_index(
                config,
                args.limit,
                args.batch_size,
                workers=args.workers,
                subject=args.subject,
                progress=reporter,
            )
            if args.price_per_million is not None:
                result["estimated_usd"] = round(
                    result["tokens"] * args.price_per_million / 1_000_000, 6
                )
        elif args.command == "migrate":
            result = migrate_legacy_index(config, args.legacy_index)
        else:
            result = search(
                args.query,
                args.mode,
                args.k,
                args.subject,
                args.grade,
                args.year,
                args.method,
                config,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")


if __name__ == "__main__":
    main()
