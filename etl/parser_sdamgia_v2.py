#!/usr/bin/env python3
"""Сбор задач по математике и физике с СДАМ ГИА в SQLite."""

import argparse
import html
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SUBJECTS = {
    "math": ("https://math-olymp.sdamgia.ru", 12691),
    "physics": ("https://phys-olymp.sdamgia.ru", 8035),
}

OUT_DIR = Path(__file__).resolve().parent / "olimpiads_data_v2"
DB_FILE = OUT_DIR / "olimpiads.sqlite3"

DELAY = 0.1
TIMEOUT = 20
WORKERS = 16
RETRIES = 3

PROBLEM_RE = re.compile(r"/problem\?(?:[^#]*&)?id=(\d+)")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def clean_line(value):
    value = html.unescape(str(value or "")).replace("\xa0", " ").replace("\xad", "")
    return re.sub(r"\s+", " ", value).strip()


def wrap_alt(value):
    value = clean_line(value)
    if not value:
        return ""
    for left, right in (("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")):
        if value.startswith(left) and value.endswith(right):
            value = value[len(left):-len(right)].strip()
            break
    return f"${value}$" if value else ""


def create_session():
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/140.0 Safari/537.36"
    )
    return session


def fetch(session, url):
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.content.decode("utf-8")


class UnavailableProblem(Exception):
    """Сайт сообщает, что доступа к задаче нет."""


def replace_images(root):
    for image in root.find_all("img"):
        image.replace_with(wrap_alt(image.get("alt")))


def node_text(node):
    return clean_line(node.get_text(" ", strip=True)) if node else ""


def parse_metadata(lines):
    candidates = [line for line in lines if "класс" in line.lower() and YEAR_RE.search(line)]
    if not candidates:
        return "", "", "", ""

    line = min(candidates, key=lambda value: ("тур" not in value.lower(), len(value)))
    year_match = YEAR_RE.search(line)
    grade_match = re.search(r"\b(\d{1,2})(?:\s*[—–-]\s*(\d{1,2}))?\s*класс", line, re.I)
    tour_match = re.search(
        r"\b(\d+\s*(?:тур|этап)\b[^,;]*)|"
        r"\b((?:школьный|муниципальный|региональный|заключительный|финальный)\s+этап)",
        line,
        re.I,
    )

    grade = ""
    olympiad = ""
    if grade_match:
        grade = grade_match.group(1)
        if grade_match.group(2):
            grade += f"-{grade_match.group(2)}"
        olympiad = clean_line(line[:grade_match.start()]).strip("? ,;:-")

    tour = clean_line(next((part for part in tour_match.groups() if part), "")) if tour_match else ""
    year = year_match.group(1) if year_match else ""
    return olympiad, grade, year, tour.strip(" ,;.")


def parse_problem(session, url):
    problem_id = PROBLEM_RE.search(url).group(1)
    html_text = fetch(session, url)
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.select_one(".prob_maindiv")
    if not main:
        page_text = clean_line(soup.get_text(" ", strip=True))
        if any(message in page_text for message in (
            "Доступ к заданию ограничен",
            "Такого задания не существует",
        )):
            raise UnavailableProblem(problem_id)
        raise ValueError("На странице нет блока .prob_maindiv")
    replace_images(main)

    info = main.select_one(".align-left")
    info_lines = [node_text(node) for node in info.find_all("div", recursive=False)] if info else []
    meta_line = next((line for line in info_lines if "класс" in line.lower()), "")
    classifier_line = next((line for line in info_lines if line.lower().startswith("классификатор")), "")
    olympiad, grade, year, tour = parse_metadata([meta_line])

    statement = node_text(main.select_one(".pbody"))
    answer = node_text(main.select_one(".answer"))
    answer = re.sub(r"^Ответ\s*:\s*", "", answer, flags=re.I)

    solution_node = main.select_one(f"#sol{problem_id}")
    if solution_node:
        for nested_answer in solution_node.select(".answer"):
            nested_answer.decompose()
    solution = node_text(solution_node)
    solution = re.sub(r"^Решени[ея]\s*[.:]?\s*", "", solution, flags=re.I)

    type_match = re.search(r"\bТип\s+(\d+)", node_text(main.select_one(".prob_nums")), re.I)

    return {
        "олимпиада": olympiad,
        "класс": grade,
        "год": year,
        "тур": tour,
        "задание": statement,
        "тип": type_match.group(1) if type_match else "",
        "классификатор": re.sub(r"^Классификатор\s*:\s*", "", classifier_line, flags=re.I),
        "решение": solution,
        "ответ": answer,
        "url": url,
        "problem_id": problem_id,
    }


def open_database(db_file=DB_FILE):
    connection = sqlite3.connect(db_file)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS problems (
            subject TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            olympiad TEXT NOT NULL DEFAULT '',
            grade TEXT NOT NULL DEFAULT '',
            year TEXT NOT NULL DEFAULT '',
            tour TEXT NOT NULL DEFAULT '',
            statement TEXT NOT NULL DEFAULT '',
            problem_type TEXT NOT NULL DEFAULT '',
            classifier TEXT NOT NULL DEFAULT '',
            solution TEXT NOT NULL DEFAULT '',
            answer TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            PRIMARY KEY (subject, problem_id)
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_problems_grade ON problems(subject, grade)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_problems_year ON problems(subject, year)")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS unavailable_ids (
            subject TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (subject, problem_id)
        )
        """
    )
    connection.commit()
    return connection


def save_problem(connection, subject, row):
    connection.execute(
        """
        INSERT INTO problems (
            subject, problem_id, olympiad, grade, year, tour, statement,
            problem_type, classifier, solution, answer, url, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(subject, problem_id) DO UPDATE SET
            olympiad=excluded.olympiad, grade=excluded.grade, year=excluded.year,
            tour=excluded.tour, statement=excluded.statement,
            problem_type=excluded.problem_type, classifier=excluded.classifier,
            solution=excluded.solution, answer=excluded.answer, url=excluded.url,
            scraped_at=excluded.scraped_at
        """,
        (
            subject, int(row["problem_id"]), row["олимпиада"], row["класс"],
            row["год"], row["тур"], row["задание"], row["тип"],
            row["классификатор"], row["решение"], row["ответ"], row["url"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    connection.commit()


def log_error(error_file, kind, url, exc):
    with error_file.open("a", encoding="utf-8") as file:
        file.write(f"{kind}\t{url}\t{exc!r}\n")


_THREAD = threading.local()


def scan_id(item):
    subject, base_url, problem_id = item
    if not hasattr(_THREAD, "session"):
        _THREAD.session = create_session()
    url = f"{base_url}/problem?id={problem_id}"
    for attempt in range(RETRIES):
        try:
            row = parse_problem(_THREAD.session, url)
            return problem_id, row, None
        except UnavailableProblem:
            return problem_id, None, None
        except Exception as exc:
            if attempt == RETRIES - 1:
                return problem_id, None, exc
            time.sleep(attempt + 1)
        finally:
            time.sleep(DELAY)


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def scan_subject(connection, pool, subject, base_url, last_id, error_file):
    done = {
        row[0] for row in connection.execute(
            "SELECT problem_id FROM problems WHERE subject = ?", (subject,)
        )
    }
    unavailable = {
        row[0] for row in connection.execute(
            "SELECT problem_id FROM unavailable_ids WHERE subject = ?", (subject,)
        )
    }
    pending = [
        (subject, base_url, problem_id)
        for problem_id in range(1, last_id + 1)
        if problem_id not in done and problem_id not in unavailable
    ]
    saved = missing = failed = 0
    print(
        f"[{subject}] ID 1–{last_id}; в БД: {len(done)}, "
        f"недоступны: {len(unavailable)}, осталось проверить: {len(pending)}",
        flush=True,
    )

    for batch in chunks(pending, 100):
        for problem_id, row, error in pool.map(scan_id, batch):
            if row:
                save_problem(connection, subject, row)
                saved += 1
            elif error:
                failed += 1
                log_error(
                    error_file, f"{subject}:PROBLEM",
                    f"{base_url}/problem?id={problem_id}", error,
                )
            else:
                connection.execute(
                    "INSERT OR IGNORE INTO unavailable_ids VALUES (?, ?, ?)",
                    (subject, problem_id, datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
                missing += 1
        checked = saved + missing + failed
        print(
            f"[{subject}] {checked}/{len(pending)}: "
            f"+{saved} задач, {missing} недоступны, {failed} ошибок",
            flush=True,
        )
    print(f"[{subject}] Сохранено всего: {len(done) + saved}", flush=True)
    return failed


def main(db_file=DB_FILE):
    db_file.parent.mkdir(parents=True, exist_ok=True)
    connection = open_database(db_file)
    error_file = db_file.with_suffix(".errors.log")
    failed = 0
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for subject, (base_url, last_id) in SUBJECTS.items():
                failed += scan_subject(
                    connection, pool, subject, base_url, last_id, error_file
                )
    finally:
        connection.close()

    print(f"\nГотово. SQLite: {db_file.resolve()}")
    return failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_FILE, help="Путь к SQLite базе")
    args = parser.parse_args()
    try:
        raise SystemExit(1 if main(args.db.resolve()) else 0)
    except KeyboardInterrupt:
        print("Остановлено пользователем. Прогресс сохранён.")
        raise SystemExit(130)
