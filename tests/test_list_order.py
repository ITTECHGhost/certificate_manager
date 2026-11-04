"""Management lists show the newest record first; lists that feed transcripts,
certificates or dropdowns keep their stage / name order."""
import ast
import sqlite3
from pathlib import Path

import pytest

from data import query

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE university_settings (id INTEGER, college_name_ar TEXT, college_name_en TEXT);
CREATE TABLE departments (id INTEGER, name_ar TEXT, name_en TEXT, university_settings_id INTEGER);
CREATE TABLE personnel (id INTEGER, name_ar TEXT, is_active INTEGER, display_order INTEGER);
CREATE TABLE courses (id INTEGER, name_ar TEXT, name_en TEXT, credit_hours INTEGER,
                      department_id INTEGER, stage_number INTEGER);
CREATE TABLE roles (id TEXT, name_ar TEXT, is_system INTEGER, created_at TEXT,
                    allowed_pages TEXT, allowed_actions TEXT);

INSERT INTO university_settings VALUES (1, 'كلية', 'College');
INSERT INTO departments VALUES (1, 'أ قسم', 'A', 1), (3, 'ب قسم', 'B', 1), (2, 'ج قسم', 'C', 1);
INSERT INTO personnel VALUES (1, 'أ', 1, 2), (5, 'ب', 1, 1), (3, 'ج', 1, 0);
INSERT INTO courses VALUES (10, 'ب مادة', 'B', 3, 1, 2), (30, 'أ مادة', 'A', 3, 1, 1), (20, 'ج مادة', 'C', 3, 1, 1);
INSERT INTO roles VALUES ('admin', 'مدير', 1, '2026-01-01', '[]', '[]'),
                         ('clerk', 'موظف', 0, '2026-02-01', '[]', '[]'),
                         ('auditor', 'مدقق', 0, '2026-03-01', '[]', '[]');
"""


@pytest.fixture
def db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    def read_all(sql, params=()):
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    monkeypatch.setattr(query, "sqlite_read_all", read_all)
    import sync_engine
    monkeypatch.setattr(sync_engine, "sqlite_read_all", read_all)
    return conn


def _ids(rows):
    return [r["id"] for r in rows]


def test_departments_newest_first(db):
    assert _ids(query.get_offline_departments()) == [3, 2, 1]


def test_personnel_newest_first(db):
    assert _ids(query.get_offline_personnel()) == [5, 3, 1]


def test_courses_management_list_newest_first(db):
    assert _ids(query.get_offline_courses_newest_first()) == [30, 20, 10]


def test_course_lists_for_transcripts_and_dropdowns_keep_stage_name_order(db):
    assert _ids(query.get_offline_courses_by_department(1)) == [30, 20, 10]   # stage 1 (أ, ج), then stage 2
    assert [r["name_ar"] for r in query.get_offline_courses()] == ["أ مادة", "ب مادة", "ج مادة"]


def test_roles_system_first_then_newest(db):
    from data.repositories.personnel import RoleRepository
    roles = RoleRepository.__new__(RoleRepository)
    assert _ids(roles._read_from_sqlite()) == ["admin", "auditor", "clerk"]


def test_study_routines_query_newest_first():
    src = (ROOT / "data" / "query.py").read_text(encoding="utf-8")
    body = src[src.index("def get_offline_study_routines"):]
    body = body[: body.index("\ndef ")]
    assert "ORDER BY sr.id DESC" in body


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found in {path.name}")


@pytest.mark.parametrize("module, func", [
    ("personnel.py", "get_personnel"),
    ("departments.py", "get_departments"),
    ("study_routines.py", "get_all_study_routines"),
])
def test_api_management_lists_newest_first(module, func):
    body = _function_source(ROOT / "certificate_manager_api" / "routers" / module, func)
    assert 'rows.sort(key=lambda r: int(r.get("id") or 0), reverse=True)' in body


def test_api_roles_system_first_then_newest():
    body = _function_source(ROOT / "certificate_manager_api" / "routers" / "personnel.py", "get_all_roles")
    assert "ORDER BY is_system DESC, created_at DESC, id DESC" in body


def test_courses_screen_uses_newest_first_list():
    src = (ROOT / "nicegui_screens" / "courses_screen.py").read_text(encoding="utf-8")
    assert "get_all_newest_first()" in src
