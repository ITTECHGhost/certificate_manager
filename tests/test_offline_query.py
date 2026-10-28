"""Offline certificate queries combine synced tables with their local_ twins.

The synced tables carry an extra updated_at column and a different column
order, so the combined subqueries must name their columns explicitly.
"""
import sqlite3

import pytest

from data import query

SCHEMA = """
CREATE TABLE students (id INTEGER, study_system_id INTEGER, updated_at TEXT);
CREATE TABLE local_students (id INTEGER, study_system_id INTEGER);
CREATE TABLE study_systems (id INTEGER, period_display TEXT);
CREATE TABLE courses (id INTEGER, name_ar TEXT, name_en TEXT, credit_hours INTEGER, stage_number INTEGER);
CREATE TABLE academic_periods (id INTEGER, student_id INTEGER, academic_year TEXT, stage_number INTEGER,
                               semester_num INTEGER, study_system_id INTEGER, result_status TEXT, updated_at TEXT);
CREATE TABLE local_academic_periods (id INTEGER, student_id INTEGER, academic_year TEXT, study_system_id INTEGER,
                                     stage_number INTEGER, semester_num INTEGER, result_status TEXT);
CREATE TABLE enrollments (id INTEGER, period_id INTEGER, course_id INTEGER, score REAL, passed_round INTEGER, updated_at TEXT);
CREATE TABLE local_enrollments (id INTEGER, period_id INTEGER, course_id INTEGER, score REAL, passed_round INTEGER);

INSERT INTO students VALUES (12, 1, '2026-01-01');
INSERT INTO study_systems VALUES (1, 'year');
INSERT INTO courses VALUES (100, 'رياضيات', 'Math', 3, 1), (200, 'فيزياء', 'Physics', 2, 2);
INSERT INTO academic_periods VALUES (1, 12, '2015', 1, 1, 9, 'PASSED', '2026-01-01');
INSERT INTO local_academic_periods VALUES (-5, 12, '2016', 9, 2, 1, 'PASSED');
INSERT INTO enrollments VALUES (1, 1, 100, 80, 1, '2026-01-01');
INSERT INTO local_enrollments VALUES (-7, -5, 200, 70, 1);
"""


@pytest.fixture
def offline_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    def read_all(sql, params=()):
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def read_one(sql, params=()):
        rows = read_all(sql, params)
        return rows[0] if rows else None

    monkeypatch.setattr(query, "sqlite_read_all", read_all)
    monkeypatch.setattr(query, "sqlite_read_one", read_one)
    return conn


def test_timeline_reads_synced_and_local_periods(offline_db):
    rows = query.sqlite_read_all(query.Q_ACADEMIC_TIMELINE, (12,))
    assert [(r["academic_year"], r["stage_number"]) for r in rows] == [
        ("2015 - 2016", 1),
        ("2016 - 2017", 2),
    ]


@pytest.mark.parametrize("mode", ["DEFAULT", "BY_PERIOD_STAGE", "BY_CURRICULUM_STAGE", "BY_ByAcademicYear"])
def test_yearly_courses_read_synced_and_local_enrollments(offline_db, mode):
    rows = query.get_offline_academic_courses(12, mode)
    assert sorted((r["course_id"], r["period_stage"]) for r in rows) == [(100, 1), (200, 2)]


@pytest.mark.parametrize("mode", ["BY_SEMESTER_stage", "DEFAULT"])
def test_semester_courses_read_synced_and_local_enrollments(offline_db, mode):
    offline_db.execute("UPDATE study_systems SET period_display = 'semester'")
    rows = query.get_offline_academic_courses(12, mode)
    assert sorted((r["course_id"], r["period_stage"]) for r in rows) == [(100, 1), (200, 2)]
