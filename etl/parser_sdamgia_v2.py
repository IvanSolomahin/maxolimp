#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Надёжный потоковый парсер math-olymp.sdamgia.ru.

Основные отличия от старой версии:
1) сохраняет положение формул/картинок в тексте через маркеры [[IMG:n]];
2) сначала берёт формулы из DOM/alt/title/data-* / MathJax / MathML;
3) SVG НИКОГДА не открывается напрямую через PIL;
4) если включён OCR, любой <img> сначала снимается браузером в PNG, и только PNG
   передаётся в pix2tex;
5) условие/решение/ответ выделяются из линейного DOM-текста по секциям;
6) метаданные ищутся по компактной строке "... класс, ... тур, ... год";
7) ошибки одной задачи не останавливают весь сбор;
8) отдельный каталог v2 не использует старый state.json с уже испорченными строками.

По умолчанию сохраняются только задачи, относящиеся к 10/11 классу.
"""

import asyncio
import csv
import html as html_lib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE = "https://math-olymp.sdamgia.ru"
START_URL = BASE + "/?redir=1"

# Отдельная папка, чтобы старый state.json не заставлял пропускать задачи,
# которые прежний парсер уже записал с потерянными формулами.
OUT = Path("olimpiads_data_v2")
HTML_DIR = OUT / "html"
IMG_DIR = OUT / "images"
CSV_FILE = OUT / "olimpiads.csv"
STATE_FILE = OUT / "state.json"
ERROR_FILE = OUT / "errors.log"
UNRESOLVED_FILE = OUT / "unresolved_images.log"

DELAY = 0.8
TARGET_GRADES = {10, 11}

# Для первой проверки лучше 20. Для полного прохода поставьте None.
TEST_LIMIT = 20

# OCR НЕ обязателен. Сначала скрипт использует данные самой страницы.
# Если после теста встретятся [[IMAGE:...]] вместо формул, можно включить True.
ENABLE_PIX2TEX = False

CSV_FIELDS = [
    "олимпиада",
    "класс",
    "год",
    "тур",
    "задание",
    "тип",
    "классификатор",
    "решение",
    "ответ",
    "url",
    "problem_id",
]

PROBLEM_URL_RE = re.compile(r"/problem\?(?:[^#]*&)?id=(\d+)")
TEST_URL_RE = re.compile(r"/test\?(?:[^#]*&)?id=(\d+)")
IMG_MARK_RE = re.compile(r"\[\[IMG:(\d+)\]\]")

# UI-картинки, которые точно не являются частью условия.
UI_IMAGE_WORDS = (
    "добавить в вариант",
    "сообщить об ошибке",
    "наверх",
    "logo",
    "логотип",
    "menu",
    "меню",
)


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = html_lib.unescape(str(s)).replace("\xa0", " ")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(s or "").replace("\xa0", " ")).strip()


def ensure_dirs():
    for p in (OUT, HTML_DIR, IMG_DIR):
        p.mkdir(parents=True, exist_ok=True)


def load_state():
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("tests", [])
                data.setdefault("problems", [])
                data.setdefault("done", [])
                data.setdefault("skipped_grade", [])
                return data
        except Exception:
            pass
    return {"tests": [], "problems": [], "done": [], "skipped_grade": []}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def append_csv(row):
    new_file = not CSV_FILE.exists()
    with CSV_FILE.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def log_error(kind, url, exc):
    with ERROR_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{kind}\t{url}\t{repr(exc)}\n")


def extract_problem_id(url):
    m = PROBLEM_URL_RE.search(url or "")
    return m.group(1) if m else ""


def normalize_math(s: str) -> str:
    s = clean_line(s)
    if not s:
        return ""

    # Убираем уже существующие внешние математические разделители,
    # чтобы не получить $$$...$$$.
    if len(s) >= 4 and s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    elif len(s) >= 2 and s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    elif s.startswith(r"\(") and s.endswith(r"\)"):
        s = s[2:-2].strip()
    elif s.startswith(r"\[") and s.endswith(r"\]"):
        s = s[2:-2].strip()

    return s


def wrap_math(s: str) -> str:
    s = normalize_math(s)
    return f"${s}$" if s else ""


def line_list(text):
    return [clean_line(x) for x in (text or "").splitlines() if clean_line(x)]


def parse_meta_line(line: str):
    """Разбирает строку вида: Олимпиада ..., 10 класс, 2 тур ..., 2016 год."""
    line = clean_line(line)
    if not line:
        return "", "", "", ""

    year = ""
    grade = ""
    tour = ""
    olymp = ""

    m = re.search(r"\b(19\d{2}|20\d{2})\s*год", line, re.I)
    if m:
        year = m.group(1)

    gm = re.search(r"\b(\d{1,2})(?:\s*[—–-]\s*(\d{1,2}))?\s*класс(?:а|ов|ы)?\b", line, re.I)
    if gm:
        grade = gm.group(1)
        if gm.group(2):
            grade = f"{gm.group(1)}-{gm.group(2)}"
        olymp = clean_line(line[:gm.start()]).strip(" ,;:-")

    tm = re.search(r"\b(\d+\s*(?:тур|этап)\b[^,;]*)", line, re.I)
    if tm:
        tour = clean_line(tm.group(1)).strip(" ,;.")
    else:
        # Иногда этап назван словами: "заключительный этап" и т.п.
        tm = re.search(r"\b((?:школьный|муниципальный|региональный|заключительный|финальный)\s+этап)\b", line, re.I)
        if tm:
            tour = clean_line(tm.group(1))

    return olymp, grade, year, tour


def find_meta(lines):
    """Ищет наиболее короткую правдоподобную строку метаданных."""
    candidates = []
    for ln in lines:
        low = ln.lower()
        if "класс" not in low:
            continue
        if not re.search(r"\b(?:19\d{2}|20\d{2})\b", ln):
            continue
        # Обычно есть тур/этап или слово олимпиада. Но не делаем это жёстким условием.
        score = len(ln)
        if "тур" in low or "этап" in low:
            score -= 100
        if "олимпи" in low:
            score -= 100
        candidates.append((score, ln))

    if not candidates:
        return "", "", "", "", ""

    candidates.sort(key=lambda x: x[0])
    meta_line = candidates[0][1]
    olymp, grade, year, tour = parse_meta_line(meta_line)
    return meta_line, olymp, grade, year, tour


def grades_from_value(grade: str):
    if not grade:
        return set()
    nums = [int(x) for x in re.findall(r"\d+", grade)]
    if not nums:
        return set()
    if len(nums) == 1:
        return {nums[0]}
    a, b = nums[0], nums[1]
    if a <= b and b - a <= 5:
        return set(range(a, b + 1))
    return set(nums)


def is_target_grade(grade: str):
    # Если класс не удалось определить, задачу НЕ выбрасываем — лучше сохранить
    # и увидеть проблему в CSV, чем потерять задачу безвозвратно.
    gs = grades_from_value(grade)
    return True if not gs else bool(gs & TARGET_GRADES)


def extract_classifier(lines):
    for i, ln in enumerate(lines):
        if re.match(r"^Классификатор\s*:", ln, re.I):
            value = re.sub(r"^Классификатор\s*:\s*", "", ln, flags=re.I)
            # Если после ':' ничего нет, захватим следующую содержательную строку.
            if not value and i + 1 < len(lines):
                value = lines[i + 1]
            return clean_line(value)
    return ""


def extract_type(text):
    m = re.search(r"\bТип\s+(\d+)\s+№\s*\d+", text or "", re.I)
    return m.group(1) if m else ""


def looks_like_solution_heading(ln):
    return bool(re.match(r"^Решени[ея]\.?\s*:??$", ln, re.I))


def extract_statement(lines):
    """Берёт текст после классификатора и до блока решения."""
    start = None

    for i, ln in enumerate(lines):
        if re.match(r"^Классификатор\s*:", ln, re.I):
            start = i + 1
            break

    if start is None:
        # Резерв: после строки метаданных.
        for i, ln in enumerate(lines):
            if "класс" in ln.lower() and re.search(r"\b(?:19\d{2}|20\d{2})\b", ln):
                start = i + 1
                break

    if start is None:
        return ""

    out = []
    for ln in lines[start:]:
        low = ln.lower()
        if low in {"i", "?"}:
            continue
        if "версия для печати" in low:
            continue
        if "спрятать решение" in low or "показать решение" in low:
            break
        if looks_like_solution_heading(ln) or re.match(r"^Решение\s*[:.]", ln, re.I):
            break
        if low.startswith("критерии проверки"):
            break
        out.append(ln)

    return clean_text("\n".join(out))


def find_solution_start(lines):
    # Приоритет — самостоятельная строка "Решение."/"Решение:"
    for i, ln in enumerate(lines):
        if looks_like_solution_heading(ln):
            return i + 1

    # Иногда заголовок и первый фрагмент решения находятся в одной строке.
    for i, ln in enumerate(lines):
        m = re.match(r"^Решени[ея]\s*[.:]\s*(.+)$", ln, re.I)
        if m:
            return i
    return None


def extract_solution(lines):
    start = find_solution_start(lines)
    if start is None:
        return ""

    out = []
    first_inline_done = False

    # Если строка start-1 была "Решение: первый текст", сохраним хвост.
    if start > 0:
        m = re.match(r"^Решени[ея]\s*[.:]\s*(.+)$", lines[start - 1], re.I)
        if m:
            out.append(clean_line(m.group(1)))
            first_inline_done = True

    scan = lines[start:]
    for ln in scan:
        low = ln.lower()
        if low in {"?", "i"}:
            continue
        if "спрятать критерии" in low or "показать критерии" in low:
            break
        if low.startswith("критерии проверки") or low.startswith("критерии оценивания"):
            break
        if re.match(r"^Ответ\s*:", ln, re.I) or low == "ответ":
            break
        # Повторная строка метаданных означает, что основной блок задачи закончился.
        if out and "класс" in low and re.search(r"\b(?:19\d{2}|20\d{2})\b", ln):
            break
        if low.startswith("решение спрятать решение"):
            break
        out.append(ln)

    return clean_text("\n".join(out))


def extract_answer(lines):
    for i, ln in enumerate(lines):
        m = re.match(r"^Ответ\s*:\s*(.*)$", ln, re.I)
        if m:
            ans = clean_line(m.group(1))
            if ans:
                return ans
            if i + 1 < len(lines):
                return clean_line(lines[i + 1])

    for i, ln in enumerate(lines):
        if ln.lower() == "ответ" and i + 1 < len(lines):
            return clean_line(lines[i + 1])
    return ""


def best_formula_from_image(img):
    """Берёт формулу из семантических атрибутов изображения, если она там есть."""
    fields = [
        img.get("data_latex", ""),
        img.get("data_tex", ""),
        img.get("aria", ""),
        img.get("alt", ""),
        img.get("title", ""),
    ]
    for raw in fields:
        val = clean_line(raw)
        if not val:
            continue
        low = val.lower()
        if any(x in low for x in UI_IMAGE_WORDS):
            continue
        # Generic "Image"/"Картинка" не является формулой.
        if low in {"image", "img", "картинка", "изображение"}:
            continue
        return val
    return ""


def likely_formula_image(img):
    attrs = " ".join(
        clean_line(str(img.get(k, "")))
        for k in ("src", "alt", "title", "class", "aria", "data_latex", "data_tex")
    ).lower()
    if re.search(r"math|formula|tex|latex|katex|mathjax|mjx", attrs):
        return True

    w = int(img.get("width") or 0)
    h = int(img.get("height") or 0)
    # Небольшие широкие изображения часто являются формулами.
    return bool(w and h and h <= 100 and w <= 1000 and w >= 20)


_PIX2TEX = None


def get_pix2tex_model():
    global _PIX2TEX
    if _PIX2TEX is None:
        from pix2tex.cli import LatexOCR
        _PIX2TEX = LatexOCR()
    return _PIX2TEX


def try_pix2tex_png(path):
    """pix2tex получает ТОЛЬКО PNG-скриншот, а не исходный SVG."""
    try:
        from PIL import Image
        model = get_pix2tex_model()
        with Image.open(path) as im:
            result = model(im.convert("RGB"))
        return normalize_math(str(result))
    except Exception as e:
        print(f"      OCR не сработал: {e}")
        return ""


async def screenshot_image_for_ocr(page, index, problem_id):
    pdir = IMG_DIR / problem_id
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / f"img_{index}.png"
    try:
        loc = page.locator("img").nth(index)
        await loc.screenshot(path=str(path), timeout=15000)
        return path
    except Exception:
        return None


async def resolve_image_markers(page, text, images, problem_id):
    """Заменяет [[IMG:n]] в ТОЧНОМ месте появления картинки."""
    if not text:
        return ""

    by_index = {int(x.get("index", -1)): x for x in images}
    cache = {}

    async def replacement(idx):
        if idx in cache:
            return cache[idx]

        img = by_index.get(idx, {})
        src = img.get("src", "")
        semantic = best_formula_from_image(img)
        if semantic:
            # Если alt уже похож на LaTeX — оформляем как математику.
            # Даже текстовое математическое описание лучше, чем потеря места формулы.
            rep = wrap_math(semantic)
            cache[idx] = rep
            return rep

        if ENABLE_PIX2TEX and likely_formula_image(img):
            png = await screenshot_image_for_ocr(page, idx, problem_id)
            if png:
                latex = try_pix2tex_png(png)
                if latex:
                    rep = wrap_math(latex)
                    cache[idx] = rep
                    return rep

        # Не угадываем содержимое. Сохраняем ссылку/маркер для последующей проверки.
        rep = f"[IMAGE:{src}]" if src else f"[IMAGE_{idx}]"
        cache[idx] = rep
        with UNRESOLVED_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{problem_id}\t{idx}\t{src}\n")
        return rep

    parts = []
    pos = 0
    for m in IMG_MARK_RE.finditer(text):
        parts.append(text[pos:m.start()])
        parts.append(await replacement(int(m.group(1))))
        pos = m.end()
    parts.append(text[pos:])
    return clean_text("".join(parts))


async def collect_links(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1000)
    return await page.locator("a").evaluate_all(
        """els => els.map(a => ({href: a.href || '', text: (a.innerText || a.textContent || '').trim()}))"""
    )


async def collect_test_links(page):
    urls = set()
    candidates = [
        START_URL,
        BASE + "/",
        BASE + "/test",
        BASE + "/prob_catalog",
        BASE + "/prob_catalog?class=10",
        BASE + "/prob_catalog?class=11",
    ]
    for url in candidates:
        try:
            links = await collect_links(page, url)
            for item in links:
                href = item.get("href", "")
                if TEST_URL_RE.search(href):
                    urls.add(urljoin(BASE, href).split("#")[0])
        except Exception as e:
            print(f"Не удалось открыть {url}: {e}")
    return sorted(urls, key=lambda u: int(TEST_URL_RE.search(u).group(1)) if TEST_URL_RE.search(u) else 10**12)


async def collect_problem_links_from_test(page, test_url):
    try:
        links = await collect_links(page, test_url)
    except Exception as e:
        print("Ошибка варианта:", test_url, e)
        return []

    result = set()
    for item in links:
        href = item.get("href", "")
        if PROBLEM_URL_RE.search(href):
            result.add(urljoin(BASE, href).split("#")[0])

    return sorted(result, key=lambda u: int(extract_problem_id(u) or 10**12))


async def extract_dom_snapshot(page, url):
    problem_id = extract_problem_id(url)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(900)

    html = await page.content()
    (HTML_DIR / f"{problem_id}.html").write_text(html, encoding="utf-8")

    # Главное изменение: walker не выбрасывает <img>, а оставляет [[IMG:index]]
    # прямо в его позиции. MathJax/MathML стараемся взять семантически.
    data = await page.locator("body").evaluate(
        r"""
        (body) => {
          const imgs = Array.from(document.images);
          const imgIndex = new Map(imgs.map((x, i) => [x, i]));
          const images = imgs.map((img, i) => ({
            index: i,
            src: img.currentSrc || img.src || '',
            alt: img.getAttribute('alt') || '',
            title: img.getAttribute('title') || '',
            aria: img.getAttribute('aria-label') || '',
            class: String(img.className || ''),
            data_latex: img.getAttribute('data-latex') || '',
            data_tex: img.getAttribute('data-tex') || '',
            width: img.naturalWidth || img.width || 0,
            height: img.naturalHeight || img.height || 0
          }));

          const BLOCK = new Set([
            'ADDRESS','ARTICLE','ASIDE','BLOCKQUOTE','DIV','DL','DT','DD','FIELDSET',
            'FIGCAPTION','FIGURE','FOOTER','FORM','H1','H2','H3','H4','H5','H6',
            'HEADER','HR','LI','MAIN','NAV','OL','P','PRE','SECTION','TABLE','TBODY',
            'TD','TFOOT','TH','THEAD','TR','UL'
          ]);

          function directMath(el) {
            const selectors = [
              "annotation[encoding='application/x-tex']",
              "script[type='math/tex']",
              "script[type='math/tex; mode=display']"
            ];
            for (const sel of selectors) {
              const x = el.matches && el.matches(sel) ? el : el.querySelector?.(sel);
              if (x && (x.textContent || '').trim()) return (x.textContent || '').trim();
            }
            for (const a of ['data-latex','data-tex','aria-label']) {
              const v = el.getAttribute?.(a);
              if (v && v.trim()) return v.trim();
            }
            return '';
          }

          function walk(node) {
            if (!node) return '';
            if (node.nodeType === Node.TEXT_NODE) return node.nodeValue || '';
            if (node.nodeType !== Node.ELEMENT_NODE) return '';

            const el = node;
            const tag = el.tagName;
            if (['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(tag)) return '';
            if (tag === 'BR') return '\n';
            if (tag === 'IMG') return ` [[IMG:${imgIndex.get(el)}]] `;

            // Для настоящих MathML/MathJax контейнеров предпочитаем исходный TeX.
            if (tag === 'MATH' || tag === 'MJX-CONTAINER' ||
                el.classList?.contains('MathJax') || el.classList?.contains('math-tex')) {
              const tex = directMath(el);
              if (tex) return ` $${tex}$ `;
            }

            let s = '';
            if (BLOCK.has(tag)) s += '\n';
            for (const ch of el.childNodes) s += walk(ch);
            if (BLOCK.has(tag)) s += '\n';
            return s;
          }

          return { linear_text: walk(body), images };
        }
        """
    )

    return {
        "problem_id": problem_id,
        "url": url,
        "linear_text": clean_text(data.get("linear_text", "")),
        "images": data.get("images", []),
    }


async def process_problem(page, url):
    data = await extract_dom_snapshot(page, url)
    pid = data["problem_id"]

    # Сначала восстанавливаем картинки/формулы В ИХ ИСХОДНЫХ ПОЗИЦИЯХ.
    resolved = await resolve_image_markers(
        page, data["linear_text"], data["images"], pid
    )
    lines = line_list(resolved)

    meta_line, olymp, grade, year, tour = find_meta(lines)
    classifier = extract_classifier(lines)
    statement = extract_statement(lines)
    solution = extract_solution(lines)
    answer = extract_answer(lines)

    return {
        "олимпиада": olymp,
        "класс": grade,
        "год": year,
        "тур": tour,
        "задание": statement,
        "тип": extract_type(resolved),
        "классификатор": classifier,
        "решение": solution,
        "ответ": answer,
        "url": url,
        "problem_id": pid,
        "_meta_line": meta_line,
    }


async def main():
    ensure_dirs()
    state = load_state()

    print("=" * 72)
    print("РЕШУ ОЛИМП — parser_sdamgia_v2")
    print("Формулы сохраняются в позиции DOM; pix2tex не обязателен.")
    print("Целевые классы: 10 и 11")
    print("=" * 72)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            ),
            locale="ru-RU",
        )
        page = await context.new_page()

        if state.get("tests"):
            test_urls = list(dict.fromkeys(state["tests"]))
            print(f"В state уже есть вариантов: {len(test_urls)}")
        else:
            print("Собираю ссылки на варианты...")
            test_urls = await collect_test_links(page)
            state["tests"] = test_urls
            save_state(state)
            print(f"Найдено вариантов: {len(test_urls)}")

        done = set(state.get("done", []))
        skipped_grade = set(state.get("skipped_grade", []))
        all_problems = set(state.get("problems", []))

        processed_this_run = 0
        stop = False

        for test_index, test_url in enumerate(test_urls, 1):
            if stop:
                break

            print("\n" + "=" * 72)
            print(f"[ВАРИАНТ {test_index}/{len(test_urls)}] {test_url}")
            print("=" * 72)

            try:
                problem_urls = await collect_problem_links_from_test(page, test_url)
            except Exception as e:
                print(f"  ❌ Не удалось получить задачи: {e}")
                log_error("TEST", test_url, e)
                continue

            print(f"  Найдено задач: {len(problem_urls)}")
            all_problems.update(problem_urls)
            state["problems"] = sorted(all_problems)
            save_state(state)

            for task_index, problem_url in enumerate(problem_urls, 1):
                pid = extract_problem_id(problem_url)

                if pid in done:
                    print(f"  [{task_index}/{len(problem_urls)}] ID {pid}: уже обработана")
                    continue
                if pid in skipped_grade:
                    print(f"  [{task_index}/{len(problem_urls)}] ID {pid}: другой класс, пропуск")
                    continue

                print(f"\n  ┌─ ЗАДАЧА {task_index}/{len(problem_urls)} (ID {pid})")
                print(f"  │  {problem_url}")

                try:
                    row = await process_problem(page, problem_url)

                    if not is_target_grade(row["класс"]):
                        skipped_grade.add(pid)
                        state["skipped_grade"] = sorted(skipped_grade)
                        save_state(state)
                        print(f"  └─ ↪ класс {row['класс'] or '?'} не относится к 10/11")
                        await asyncio.sleep(DELAY)
                        continue

                    print("  │  условие:", "✓" if row["задание"] else "❌")
                    print("  │  решение:", "✓" if row["решение"] else "⚠️")
                    print("  │  ответ:", "✓" if row["ответ"] else "⚠️ (может отсутствовать на сайте)")
                    print("  │  олимпиада:", row["олимпиада"] or "⚠️")
                    print("  │  класс:", row["класс"] or "⚠️")
                    print("  │  год:", row["год"] or "⚠️")
                    print("  │  тур:", row["тур"] or "⚠️")
                    print("  │  тип:", row["тип"] or "⚠️")

                    # В CSV не пишем служебное поле.
                    row.pop("_meta_line", None)
                    append_csv(row)

                    done.add(pid)
                    state["done"] = sorted(done)
                    save_state(state)
                    processed_this_run += 1
                    print("  └─ ✓ СОХРАНЕНО В CSV")

                    if TEST_LIMIT is not None and processed_this_run >= TEST_LIMIT:
                        print(f"\nДостигнут TEST_LIMIT={TEST_LIMIT}. Тестовый запуск завершён.")
                        stop = True
                        break

                except Exception as e:
                    print(f"  └─ ❌ ОШИБКА: {repr(e)}")
                    log_error("PROBLEM", problem_url, e)

                await asyncio.sleep(DELAY)

        await browser.close()

    print("\n" + "=" * 72)
    print("ГОТОВО")
    print(f"CSV: {CSV_FILE.resolve()}")
    print(f"HTML: {HTML_DIR.resolve()}")
    print(f"Неразобранные изображения: {UNRESOLVED_FILE.resolve()}")
    print(f"State: {STATE_FILE.resolve()}")
    print("=" * 72)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановлено пользователем. Прогресс уже сохранён.")
    except Exception as e:
        print("\nКРИТИЧЕСКАЯ ОШИБКА:", repr(e))
        sys.exit(1)
