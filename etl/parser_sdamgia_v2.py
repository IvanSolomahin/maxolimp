#!/usr/bin/env python3
"""Сбор задач по математике и физике с olymp.sdamgia.ru в SQLite."""

import html
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SUBJECTS = {
    "math": "https://math-olymp.sdamgia.ru",
    "physics": "https://phys-olymp.sdamgia.ru",
}

OUT_DIR = Path("olimpiads_data_v2")
DB_FILE = OUT_DIR / "olimpiads.sqlite3"
ERROR_FILE = OUT_DIR / "errors.log"

DELAY = 0.2
TIMEOUT = 60

PROBLEM_RE = re.compile(r"/problem\?(?:[^#]*&)?id=(\d+)")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def clean_line(value):
    value = html.unescape(str(value or "")).replace("\xa0", " ").replace("\xad", "")
    return re.sub(r"\s+", " ", value).strip()


def clean_text(value):
    lines = [clean_line(line) for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line)


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


def soup_from(html_text):
    return BeautifulSoup(html_text, "html.parser")


def links_matching(soup, pattern, base_url):
    urls = set()
    for tag in soup.find_all("a", href=True):
        url = urljoin(base_url, tag["href"]).split("#", 1)[0]
        if pattern.search(url):
            urls.add(url)
    return urls


def collect_test_urls(session, base_url):
    """Получает тематические страницы задач из API React-каталога."""
    response = session.post(f"{base_url}/newapi/catalog/types", json={}, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    urls = set()

    def visit(node):
        if isinstance(node, dict):
            href = node.get("href", "")
            if href.startswith("/test?"):
                separator = "&" if "?" in href else "?"
                if "filter=" not in href:
                    href += f"{separator}filter=all"
                urls.add(urljoin(base_url, href))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(data.get("types", []))
    return sorted(urls)


def collect_problem_urls(session, test_url, base_url):
    soup = soup_from(fetch(session, test_url))
    return sorted(
        links_matching(soup, PROBLEM_RE, base_url),
        key=lambda url: int(PROBLEM_RE.search(url).group(1)),
    )


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
    soup = soup_from(html_text)
    main = soup.select_one(".prob_maindiv")
    if not main:
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


def open_database():
    connection = sqlite3.connect(DB_FILE)
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


def log_error(kind, url, exc):
    with ERROR_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{kind}\t{url}\t{exc!r}\n")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    session = create_session()
    connection = open_database()

    try:
        for subject, base_url in SUBJECTS.items():
            print(f"\n[{subject}] Получаю каталог...", flush=True)
            test_urls = collect_test_urls(session, base_url)
            print(f"[{subject}] Разделов каталога: {len(test_urls)}", flush=True)

            problem_urls = set()
            for index, test_url in enumerate(test_urls, 1):
                try:
                    problem_urls.update(collect_problem_urls(session, test_url, base_url))
                except Exception as exc:
                    log_error(f"{subject}:TEST", test_url, exc)
                if index % 20 == 0 or index == len(test_urls):
                    print(
                        f"[{subject}] Каталог {index}/{len(test_urls)}, "
                        f"уникальных задач: {len(problem_urls)}",
                        flush=True,
                    )

            done = {
                row[0] for row in connection.execute(
                    "SELECT problem_id FROM problems WHERE subject = ?", (subject,)
                )
            }
            pending = sorted(
                (url for url in problem_urls if int(PROBLEM_RE.search(url).group(1)) not in done),
                key=lambda url: int(PROBLEM_RE.search(url).group(1)),
            )
            print(
                f"[{subject}] Всего: {len(problem_urls)}, уже в БД: {len(done)}, "
                f"осталось: {len(pending)}",
                flush=True,
            )

            for index, url in enumerate(pending, 1):
                problem_id = PROBLEM_RE.search(url).group(1)
                try:
                    save_problem(connection, subject, parse_problem(session, url))
                except Exception as exc:
                    print(f"[{subject}] Ошибка задачи {problem_id}: {exc}", flush=True)
                    log_error(f"{subject}:PROBLEM", url, exc)
                if index % 25 == 0 or index == len(pending):
                    print(f"[{subject}] Задачи {index}/{len(pending)}", flush=True)
                time.sleep(DELAY)
    finally:
        connection.close()

    print(f"\nГотово. SQLite: {DB_FILE.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Остановлено пользователем. Прогресс сохранён.")
