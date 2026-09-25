"""Import the ETL SQLite snapshot into an initialized service PostgreSQL database.

Run from task_find_service: python import_etl.py --sqlite ../etl/olimpiads_data_v2/olimpiads.sqlite3
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import sqlite3
import struct
import uuid

from sqlalchemy import text

from app.db import SessionLocal


SOURCE = "sdamgia"
MODEL = "qwen/qwen3-embedding-4b"
NAMESPACE = uuid.UUID("571af4f5-0431-43d7-9638-23086221ba43")


def task_id(subject: str, problem_id: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{SOURCE}:{subject}:{problem_id}")


def solution_id(subject: str, problem_id: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{SOURCE}:{subject}:{problem_id}:solution")


def optional_int(value: str) -> int | None:
    return int(value) if value.strip() else None


def chunks(cursor, size: int):
    while rows := cursor.fetchmany(size):
        yield rows


async def import_snapshot(path: Path, batch_size: int = 200) -> None:
    source = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        async with SessionLocal() as session:
            names = [row[0] for row in source.execute(
                "SELECT DISTINCT olympiad FROM problems WHERE trim(olympiad) != ''"
            )]
            await session.execute(text("""
                INSERT INTO olympiads(id, name, short_name) VALUES (:id, :name, NULL)
                ON CONFLICT(name) DO NOTHING
            """), [{"id": uuid.uuid5(NAMESPACE, "olympiad:" + name), "name": name} for name in names])
            await session.commit()
            olympiads = dict((row.name, row.id) for row in (
                await session.execute(text("SELECT id, name FROM olympiads WHERE name = ANY(:names)"), {"names": names})
            ).all())
            await session.commit()

            count = 0
            for rows in chunks(source.execute("SELECT * FROM problems ORDER BY subject, problem_id"), batch_size):
                tasks, refs, solutions, links, removed_solutions = [], [], [], [], []
                for row in rows:
                    ident = task_id(row["subject"], row["problem_id"])
                    tasks.append({
                        "id": ident, "statement": row["statement"],
                        "answer": row["answer"] or None,
                        "subject": row["subject"], "grade": optional_int(row["grade"]),
                        "problem_type": row["problem_type"],
                        "classifier": row["classifier"], "difficulty": row["difficulty"],
                        "stage": row["tour"] or None, "year": optional_int(row["year"]),
                        "number": str(row["problem_id"]),
                        "status": "published" if row["statement"].strip() else "draft",
                    })
                    refs.append({
                        "id": ident, "subject": row["subject"],
                        "external_id": str(row["problem_id"]), "url": row["url"],
                        "scraped_at": datetime.fromisoformat(row["scraped_at"]),
                    })
                    if row["solution"].strip():
                        solutions.append({"id": solution_id(row["subject"], row["problem_id"]),
                                          "task_id": ident, "content": row["solution"]})
                    else:
                        removed_solutions.append(solution_id(row["subject"], row["problem_id"]))
                    if row["olympiad"].strip():
                        links.append({"task_id": ident, "olympiad_id": olympiads[row["olympiad"]]})
                async with session.begin():
                    await session.execute(text("""
                        INSERT INTO tasks(id, statement, answer, subject, grade, problem_type,
                            classifier, difficulty, source_stage, source_year,
                            source_problem_number, status)
                        VALUES (:id, :statement, :answer, :subject, :grade, :problem_type,
                            :classifier, :difficulty, :stage, :year, :number, :status)
                        ON CONFLICT(id) DO UPDATE SET
                            statement = EXCLUDED.statement, answer = EXCLUDED.answer,
                            subject = EXCLUDED.subject, grade = EXCLUDED.grade,
                            problem_type = EXCLUDED.problem_type, classifier = EXCLUDED.classifier,
                            difficulty = EXCLUDED.difficulty, source_stage = EXCLUDED.source_stage,
                            source_year = EXCLUDED.source_year, status = EXCLUDED.status
                    """), tasks)
                    await session.execute(text("""
                        INSERT INTO task_sources(task_id, source_system, subject, external_id, url, scraped_at)
                        VALUES (:id, 'sdamgia', :subject, :external_id, :url, :scraped_at)
                        ON CONFLICT(source_system, subject, external_id) DO UPDATE SET
                            url = EXCLUDED.url, scraped_at = EXCLUDED.scraped_at
                    """), refs)
                    if solutions:
                        await session.execute(text("""
                            INSERT INTO solutions(id, task_id, content, is_generated, is_verified)
                            VALUES (:id, :task_id, :content, false, false)
                            ON CONFLICT(id) DO UPDATE SET content = EXCLUDED.content
                        """), solutions)
                    if removed_solutions:
                        await session.execute(text("DELETE FROM solutions WHERE id = ANY(:ids)"), {"ids": removed_solutions})
                    if links:
                        await session.execute(text("""
                            INSERT INTO task_olympiads(task_id, olympiad_id)
                            VALUES (:task_id, :olympiad_id) ON CONFLICT DO NOTHING
                        """), links)
                count += len(rows)
                if count % 2000 < batch_size:
                    print(f"tasks: {count}", flush=True)

            vectors = 0
            source_embeddings = set()
            for rows in chunks(source.execute("SELECT * FROM search_vectors WHERE model = ? AND dimensions = 2560", (MODEL,)), batch_size):
                items = []
                for row in rows:
                    blob = row["vector"]
                    if len(blob) != 2560 * 4:
                        raise ValueError(f"Wrong vector size: {row['subject']}:{row['problem_id']}")
                    values = struct.unpack("<2560f", blob)
                    items.append({
                        "task_id": task_id(row["subject"], row["problem_id"]),
                        "kind": row["kind"], "model": row["model"],
                        "dimensions": row["dimensions"], "text_hash": row["text_hash"],
                        "embedding": "[" + ",".join(map(str, values)) + "]",
                    })
                    source_embeddings.add((task_id(row["subject"], row["problem_id"]), row["kind"]))
                async with session.begin():
                    await session.execute(text("""
                        INSERT INTO task_embeddings(task_id, kind, model, dimensions, text_hash, embedding)
                        VALUES (:task_id, :kind, :model, :dimensions, :text_hash,
                            CAST(:embedding AS vector))
                        ON CONFLICT(task_id, kind, model, dimensions) DO UPDATE SET
                            text_hash = EXCLUDED.text_hash, embedding = EXCLUDED.embedding,
                            updated_at = now()
                        WHERE task_embeddings.text_hash IS DISTINCT FROM EXCLUDED.text_hash
                    """), items)
                vectors += len(rows)
                if vectors % 4000 < batch_size:
                    print(f"vectors: {vectors}", flush=True)
            present = (await session.execute(text("""
                SELECT e.task_id, e.kind FROM task_embeddings e
                JOIN task_sources s ON s.task_id = e.task_id
                WHERE s.source_system = 'sdamgia' AND e.model = :model
            """), {"model": MODEL})).all()
            stale = [{"task_id": ident, "kind": kind, "model": MODEL}
                     for ident, kind in present if (ident, kind) not in source_embeddings]
            await session.commit()
            for offset in range(0, len(stale), batch_size):
                async with session.begin():
                    await session.execute(text("""
                        DELETE FROM task_embeddings
                        WHERE task_id = :task_id AND kind = :kind AND model = :model
                    """), stale[offset:offset + batch_size])
            print(f"Imported {count} tasks and {vectors} vectors")
    finally:
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(import_snapshot(args.sqlite, args.batch_size))


if __name__ == "__main__":
    main()
