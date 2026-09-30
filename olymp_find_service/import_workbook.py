"""Build a deterministic, transactional SQL seed from olympiads_benefits.xlsx.

The workbook supplies data only. Its cells are never executed as instructions.
Usage: python3 import_workbook.py INPUT.xlsx OUTPUT.sql
"""
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

COLUMNS = {
    1: ("university", ("id", "name")),
    2: ("universities_cities", ("university_id", "city_id")),
    3: ("city", ("id", "name")),
    4: ("programs_universities", ("program_id", "university_id")),
    5: ("program", ("id", "name", "code")),
    6: ("subject", ("id", "name")),
    7: ("subject_olympiad", ("id", "subject_id", "olympiad_id")),
    8: ("olympiad", ("id", "host_university_id", "name", "complexity", "description")),
    9: ("stage", ("stage_id", "olymp_id", "name", "is_online", "location", "start_date", "end_date")),
    10: ("benefit", ("id", "olympiad_id", "program_id", "university_id", "benefit_type")),
}
ORDER = (1, 3, 2, 5, 4, 6, 8, 7, 9, 10)
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Missing subject_olympiad rows whose description directly names the subject(s).
# IDs refer to the workbook's olympiad and subject sheets.
CONFIRMED_MISSING_SUBJECTS = {
    "73": ("233",),  # financial literacy
    "74": ("233",),
    "83": ("233",),
    "85": ("101",),  # nanotechnology
    "90": ("105",),  # education and pedagogical sciences
    "92": ("10",),   # chemistry
    "93": ("10",),
    "100": ("7",),   # mathematics
    "102": ("17",),  # economics
    "103": ("6", "7", "8", "9", "14", "115", "232", "248"),
    "107": ("7", "18"),
    "113": ("5", "7", "48"),
    "115": ("2",),   # geography
    "116": ("10",),  # chemistry
    "119": ("17",),  # economics
}


def read_workbook(path):
    result = {}
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//x:t", NS)) for si in root.findall("x:si", NS)]
        for sheet_no in COLUMNS:
            root = ET.fromstring(archive.read(f"xl/worksheets/sheet{sheet_no}.xml"))
            raw_rows = root.findall(".//x:sheetData/x:row", NS)
            rows = []
            for row in raw_rows:
                values = {}
                for cell in row.findall("x:c", NS):
                    value = cell.find("x:v", NS)
                    inline = cell.find("x:is", NS)
                    content = value.text if value is not None else (
                        "".join(t.text or "" for t in inline.findall(".//x:t", NS)) if inline is not None else None
                    )
                    if cell.get("t") == "s" and content is not None:
                        content = shared[int(content)]
                    if content is not None:
                        values[re.match(r"[A-Z]+", cell.get("r")).group()] = content
                rows.append(values)
            headers = rows[0]
            expected = set(COLUMNS[sheet_no][1]) - ({"id"} if sheet_no == 7 else set())
            if set(headers.values()) != expected:
                raise ValueError(f"Unexpected columns on sheet {sheet_no}: {headers}")
            result[sheet_no] = [{headers[col]: value for col, value in row.items() if col in headers} for row in rows[1:]]
    result[7] = [dict(id=str(i), **row) for i, row in enumerate(result[7], 1)]
    existing = {(row["olympiad_id"], row["subject_id"]) for row in result[7]}
    next_id = len(result[7]) + 1
    for olympiad_id, subject_ids in CONFIRMED_MISSING_SUBJECTS.items():
        for subject_id in subject_ids:
            if (olympiad_id, subject_id) not in existing:
                result[7].append({"id": str(next_id), "olympiad_id": olympiad_id, "subject_id": subject_id})
                existing.add((olympiad_id, subject_id))
                next_id += 1
    return result


def validate(sheets):
    for sheet_no, (_, columns) in COLUMNS.items():
        for row in sheets[sheet_no]:
            if not set(row) <= set(columns):
                raise ValueError(f"Unexpected data on sheet {sheet_no}")
        if "id" in columns:
            ids = [row["id"] for row in sheets[sheet_no]]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate IDs on sheet {sheet_no}")
    for sheet_no, column, target in ((2,"university_id",1),(2,"city_id",3),(4,"program_id",5),
                                      (4,"university_id",1),(7,"subject_id",6),(7,"olympiad_id",8),
                                      (8,"host_university_id",1),(9,"olymp_id",8),(10,"olympiad_id",8),
                                      (10,"program_id",5),(10,"university_id",1)):
        missing = {r[column] for r in sheets[sheet_no] if column in r} - {r["id"] for r in sheets[target]}
        if missing:
            raise ValueError(f"Missing references on sheet {sheet_no}: {column}={missing}")
    for sheet_no, columns in ((2,("university_id","city_id")),(4,("program_id","university_id")),
                              (7,("subject_id","olympiad_id"))):
        keys = [tuple(r[c] for c in columns) for r in sheets[sheet_no]]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate pairs on sheet {sheet_no}")
    for sheet_no, column in ((5,"code"),(8,"name")):
        keys = [r[column] for r in sheets[sheet_no] if column in r]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate {column} on sheet {sheet_no}")
    if {r["benefit_type"] for r in sheets[10]} - {"no entrance exams", "100 points", "additional_points"}:
        raise ValueError("Unknown benefit type")


def literal(value):
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def build_sql(sheets):
    statements = [
        "BEGIN;",
        "ALTER TABLE program ALTER COLUMN name DROP NOT NULL;",
        "ALTER TABLE program ALTER COLUMN code DROP NOT NULL;",
        "ALTER TABLE olympiad ALTER COLUMN host_university_id DROP NOT NULL;",
        "ALTER TABLE olympiad ALTER COLUMN complexity DROP NOT NULL;",
        "ALTER TABLE olympiad ALTER COLUMN description DROP NOT NULL;",
        "TRUNCATE benefit, stage, subject_olympiad, olympiad, subject, programs_universities, program, universities_cities, city, university RESTART IDENTITY CASCADE;",
    ]
    for sheet_no in ORDER:
        table, columns = COLUMNS[sheet_no]
        rows = sheets[sheet_no]
        for start in range(0, len(rows), 500):
            batch = rows[start:start+500]
            values = ",\n".join("(" + ", ".join(literal(row.get(col)) for col in columns) + ")" for row in batch)
            statements.append(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n{values};")
    for table, pk in (("university","id"),("city","id"),("program","id"),("subject","id"),
                      ("olympiad","id"),("subject_olympiad","id"),("stage","stage_id"),("benefit","id")):
        statements.append(f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), COALESCE((SELECT MAX({pk}) FROM {table}), 1), (SELECT COUNT(*) > 0 FROM {table}));")
    statements.append("COMMIT;")
    return "\n\n".join(statements) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 import_workbook.py INPUT.xlsx OUTPUT.sql")
    sheets = read_workbook(sys.argv[1])
    validate(sheets)
    Path(sys.argv[2]).write_text(build_sql(sheets), encoding="utf-8")
    print("Rows: " + ", ".join(f"{COLUMNS[i][0]}={len(sheets[i])}" for i in ORDER))
