#!/usr/bin/env python3
"""Fill problems.difficulty (1-10) with TypeSafe Jev via OpenRouter."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import os
from pathlib import Path
import random
import sqlite3
import sys
import time

import requests

from scrape.parser_sdamgia_v2 import DB_FILE

API_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
DEFAULT_KEY_FILE = DB_FILE.parent / "openrouter.key"
DEFAULT_PROXY = os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:12334"
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 520, 522, 524, 529}
LEVELS = [
    "Самая доступная олимпиадная задача: достаточно заметить один простой ход; сюда же попадают задачи, сводящиеся к обычному школьному упражнению.",
    "Один знакомый олимпиадный приём, который легко распознать по условию; после выбора приёма решение короткое.",
    "Нужно самостоятельно распознать подходящий приём и аккуратно довести несколько шагов до ответа.",
    "Нужны два стандартных приёма или простая промежуточная конструкция; ключевой ход доступен подготовленному участнику.",
    "Полноценная олимпиадная задача средней сложности: требуется выбрать путь решения и связать несколько содержательных шагов.",
    "Один существенно неочевидный ключевой ход, за которым следует нетривиальное, но прямое развитие решения.",
    "Ключевой ход трудно обнаружить; кроме него нужна самостоятельная работа с дополнительным препятствием или особым случаем.",
    "Нужны две разные неочевидные идеи либо одна глубокая идея и сложное её обоснование; стандартные подходы не дают полного решения.",
    "Требуется сложный синтез нескольких идей или необычная смена представления задачи с тонким доказательством; задача очень трудна для сильного участника.",
    "Исключительная олимпиадная задача: оригинальная глубокая идея и несколько трудных шагов её реализации; даже сильные участники обычно не находят полного решения.",
]
INSTRUCTIONS = (
    "Оцени сложность самостоятельного нахождения решения внутри диапазона "
    "олимпиадных задач указанного класса для подготовленного участника. "
    "Уровень 1 — нижняя граница этого диапазона; обычное школьное упражнение "
    "тоже относится к уровню 1. Если класс не указан, ориентируйся на 10 класс. "
    "Используй решение только для понимания необходимых идей. Не считай длину "
    "текста, объём вычислений и оформление решающими признаками. Выбери "
    "уровень по характеру требуемого рассуждения."
)


def payload_for(row):
    state = {
        "subject": {"math": "математика", "physics": "физика"}.get(
            row["subject"], row["subject"]
        ),
        "grade": row["grade"].strip() or "не указан",
        "statement": row["statement"].strip(),
    }
    if row["solution"].strip():
        state["solution"] = row["solution"].strip()
    return {
        "model": MODEL,
        "state": state,
        "questions": {
            "difficulty": {
                "type": "score",
                "instructions": INSTRUCTIONS,
                "criteria": LEVELS,
            }
        },
    }


def parse_score(body):
    if not isinstance(body, dict):
        raise ValueError("OpenRouter вернул не объект JSON")
    answers = body.get("answers")
    answer = answers.get("difficulty") if isinstance(answers, dict) else None
    if not isinstance(answer, dict) or answer.get("type") != "score":
        raise ValueError("В ответе нет difficulty типа score")
    score = answer.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("В ответе нет числового score")
    if not math.isfinite(score) or not 0 <= score <= 9:
        raise ValueError(f"score вне диапазона 0–9: {score}")
    return float(score)


def score_to_difficulty(score):
    return min(10, math.floor(score + 0.5) + 1)


def parse_difficulty(body):
    return score_to_difficulty(parse_score(body))


def score_one(row, api_key, proxy, attempts=6):
    payload = payload_for(row)
    proxies = {"http": proxy, "https": proxy}
    with requests.Session() as session:
        session.trust_env = False
        for attempt in range(attempts):
            try:
                response = session.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                    proxies=proxies,
                    timeout=120,
                )
            except requests.RequestException:
                if attempt == attempts - 1:
                    raise
                time.sleep(min(30, 2**attempt) + random.uniform(0, 0.5))
                continue
            if response.status_code in RETRYABLE_STATUS:
                if attempt == attempts - 1:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 2**attempt
                time.sleep(min(60, max(0, delay)) + random.uniform(0, 0.5))
                continue
            response.raise_for_status()
            return parse_score(response.json())
    raise RuntimeError("Не удалось получить оценку")


def label_one(row, api_key, proxy, attempts=6):
    return score_to_difficulty(score_one(row, api_key, proxy, attempts))


def ensure_column(connection):
    columns = {row[1] for row in connection.execute("PRAGMA table_info(problems)")}
    if not columns:
        raise RuntimeError("В базе нет таблицы problems")
    if "difficulty" not in columns:
        connection.execute(
            "ALTER TABLE problems ADD COLUMN difficulty INTEGER "
            "CHECK (difficulty BETWEEN 1 AND 10)"
        )
        connection.commit()


def print_progress(done, total, failed, start, final=False):
    elapsed = max(time.monotonic() - start, 0.001)
    speed = done / elapsed
    eta = (total - done) / speed if speed else 0
    line = (
        f"Обработано {done}/{total} ({done / total:.1%}); ошибок {failed}; "
        f"{speed:.1f} задач/с; осталось ~{eta / 60:.1f} мин"
    )
    if sys.stderr.isatty():
        print("\r" + line + ("\n" if final else ""), end="", file=sys.stderr, flush=True)
    else:
        print(line, file=sys.stderr, flush=True)


def run(args):
    if args.api_key_file:
        api_key = args.api_key_file.read_text(encoding="utf-8").strip()
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key and DEFAULT_KEY_FILE.is_file():
            api_key = DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError(
            "Нужен OPENROUTER_API_KEY, --api-key-file "
            f"или ключ в {DEFAULT_KEY_FILE}"
        )
    if not args.proxy:
        raise ValueError("Нужен адрес локального прокси в --proxy или HTTPS_PROXY")
    if args.batch_size < 1 or args.workers < 1 or args.limit is not None and args.limit < 1:
        raise ValueError("batch-size, workers и limit должны быть положительными")

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    try:
        ensure_column(connection)
        where = "difficulty IS NULL AND trim(statement) <> ''"
        params = []
        if args.subject:
            where += " AND subject = ?"
            params.append(args.subject)
        rows = connection.execute(
            f"SELECT subject, problem_id, grade, statement, solution "
            f"FROM problems WHERE {where} ORDER BY subject, problem_id",
            params,
        ).fetchall()
        if args.limit:
            rows = rows[: args.limit]
        total = len(rows)
        if not total:
            print("Нет задач для разметки.")
            return 0
        print(
            f"Задач: {total}; batch: {args.batch_size}; потоков: {args.workers}; "
            f"прокси: {args.proxy}",
            file=sys.stderr,
        )
        done = failed = 0
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            for offset in range(0, total, args.batch_size):
                batch = rows[offset : offset + args.batch_size]
                fatal_error = None
                futures = {
                    executor.submit(label_one, row, api_key, args.proxy): row
                    for row in batch
                }
                for future in as_completed(futures):
                    row = futures[future]
                    try:
                        difficulty = future.result()
                    except Exception as exc:
                        failed += 1
                        if isinstance(exc, requests.HTTPError) and exc.response is not None:
                            if exc.response.status_code in {400, 401, 402, 403, 404}:
                                fatal_error = exc
                        print(
                            f"\nОшибка {row['subject']}/{row['problem_id']}: {exc}",
                            file=sys.stderr,
                        )
                    else:
                        connection.execute(
                            "UPDATE problems SET difficulty = ? "
                            "WHERE subject = ? AND problem_id = ? AND difficulty IS NULL",
                            (difficulty, row["subject"], row["problem_id"]),
                        )
                        connection.commit()
                    done += 1
                print_progress(done, total, failed, start, final=offset + len(batch) == total)
                if fatal_error is not None:
                    raise fatal_error
        print(f"Готово: {done - failed} оценено, {failed} ошибок.")
        return 1 if failed else 0
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_FILE)
    parser.add_argument(
        "--api-key-file", type=Path,
        help="Файл с ключом; иначе OPENROUTER_API_KEY или локальный openrouter.key",
    )
    parser.add_argument(
        "--proxy", default=DEFAULT_PROXY,
        help=f"Локальный HTTP-прокси (по умолчанию HTTPS_PROXY или {DEFAULT_PROXY})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Число задач в одной группе запросов (по умолчанию 32)",
    )
    parser.add_argument("--workers", type=int, default=8, help="Одновременные запросы")
    parser.add_argument("--subject", choices=("math", "physics"))
    parser.add_argument("--limit", type=int, help="Оценить только первые N неразмеченных задач")
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, sqlite3.Error, ValueError, requests.RequestException) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
