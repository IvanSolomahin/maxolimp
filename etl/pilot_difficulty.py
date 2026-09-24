#!/usr/bin/env python3
"""Random, reproducible Jev pilot; stores results outside the source database."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import random
import sqlite3
import sys
import time

from label_difficulty import DEFAULT_KEY_FILE, DEFAULT_PROXY, score_one, score_to_difficulty
from parser_sdamgia_v2 import DB_FILE


def initialize(source, output, per_subject, repeats, seed):
    output.execute("""CREATE TABLE IF NOT EXISTS sample (
        subject TEXT NOT NULL, problem_id INTEGER NOT NULL,
        grade TEXT, olympiad TEXT, year TEXT, tour TEXT,
        statement TEXT, solution TEXT,
        repeat_requested INTEGER NOT NULL,
        PRIMARY KEY (subject, problem_id)
    )""")
    output.execute("""CREATE TABLE IF NOT EXISTS scores (
        subject TEXT NOT NULL, problem_id INTEGER NOT NULL,
        run INTEGER NOT NULL CHECK (run IN (1, 2)),
        raw_score REAL NOT NULL, difficulty INTEGER NOT NULL,
        PRIMARY KEY (subject, problem_id, run)
    )""")
    output.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    expected = {"source": str(source.resolve()), "per_subject": str(per_subject),
                "repeats": str(repeats), "seed": str(seed)}
    existing = dict(output.execute("SELECT key, value FROM settings"))
    if existing:
        if existing != expected:
            raise ValueError("Параметры не совпадают с существующим файлом пилота")
        return

    rng = random.Random(seed)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        selected = []
        for subject in ("math", "physics"):
            rows = db.execute(
                "SELECT subject, problem_id, grade, olympiad, year, tour, statement, solution "
                "FROM problems WHERE subject = ? AND trim(statement) <> ''",
                (subject,),
            ).fetchall()
            if len(rows) < per_subject:
                raise ValueError(f"Недостаточно задач по предмету {subject}")
            selected.extend(rng.sample(rows, per_subject))
    if repeats > len(selected):
        raise ValueError("Число повторов больше размера выборки")
    repeat_ids = {(row["subject"], row["problem_id"]) for row in rng.sample(selected, repeats)}
    with output:
        output.executemany("INSERT INTO settings VALUES (?, ?)", expected.items())
        output.executemany(
            "INSERT INTO sample VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(row["subject"], row["problem_id"], row["grade"], row["olympiad"],
              row["year"], row["tour"], row["statement"], row["solution"],
              int((row["subject"], row["problem_id"]) in repeat_ids))
             for row in selected],
        )


def run(args):
    if args.per_subject < 1 or args.repeats < 0 or args.workers < 1:
        raise ValueError("Размер выборки и число потоков должны быть положительными")
    if args.api_key_file:
        api_key = args.api_key_file.read_text(encoding="utf-8").strip()
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key and DEFAULT_KEY_FILE.is_file():
            api_key = DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError("Не найден ключ OpenRouter")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.output) as output:
        output.row_factory = sqlite3.Row
        initialize(args.db, output, args.per_subject, args.repeats, args.seed)
        tasks = output.execute("""
            SELECT s.*, 1 AS run FROM sample s
            WHERE NOT EXISTS (SELECT 1 FROM scores x
                              WHERE x.subject=s.subject AND x.problem_id=s.problem_id AND x.run=1)
            UNION ALL
            SELECT s.*, 2 AS run FROM sample s
            WHERE s.repeat_requested=1
              AND NOT EXISTS (SELECT 1 FROM scores x
                              WHERE x.subject=s.subject AND x.problem_id=s.problem_id AND x.run=2)
        """).fetchall()
        if not tasks:
            print("Пилот уже завершён.")
            return
        # Run all first ratings before repeats; the second pass is a separate request.
        tasks = sorted(tasks, key=lambda row: row["run"])
        print(f"Запросов: {len(tasks)}; потоков: {args.workers}; результаты: {args.output}", flush=True)
        start = time.monotonic()
        failed = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(score_one, row, api_key, args.proxy): row for row in tasks
            }
            for done, future in enumerate(as_completed(futures), 1):
                row = futures[future]
                try:
                    score = future.result()
                except Exception as exc:
                    failed += 1
                    print(f"Ошибка {row['subject']}/{row['problem_id']} повтор {row['run']}: {exc}",
                          file=sys.stderr, flush=True)
                else:
                    with output:
                        output.execute("INSERT INTO scores VALUES (?, ?, ?, ?, ?)",
                                       (row["subject"], row["problem_id"], row["run"],
                                        score, score_to_difficulty(score)))
                if done % 10 == 0 or done == len(tasks):
                    elapsed = max(time.monotonic() - start, .001)
                    print(f"{done}/{len(tasks)}; ошибок {failed}; "
                          f"{done / elapsed:.1f} запросов/с", flush=True)
        if failed:
            raise RuntimeError(f"Не удалось оценить {failed} задач; повторный запуск продолжит пилот")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_FILE)
    parser.add_argument("--output", type=Path, default=Path("experiments/jev_pilot.sqlite3"))
    parser.add_argument("--per-subject", type=int, default=150)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--api-key-file", type=Path)
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, sqlite3.Error, RuntimeError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
