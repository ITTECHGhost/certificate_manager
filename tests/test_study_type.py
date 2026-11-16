"""Migration 0006: «نوع الدراسة» (morning / evening / parallel) is saved on the student,
apart from «نظام الدراسة»; old clients (2.5.2, 2.5.3) keep working with the new server."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, "certificate_manager_api")
sys.path.insert(0, API)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _flat(sql: str) -> str:
    """No backticks, single spaces: so a check does not depend on formatting."""
    return re.sub(r"\s+", " ", sql.replace("`", ""))


# ── The helper ───────────────────────────────────────────────────────────────

def test_helper_copies_are_identical():
    assert _read("utils", "study_type.py") == _read("certificate_manager_api", "study_type.py")


def test_normalize_study_type():
    from utils.study_type import normalize_study_type
    assert normalize_study_type("Evening") == "evening"
    assert normalize_study_type(" مسائي ") == "evening"
    assert normalize_study_type("المسائية") == "evening"
    assert normalize_study_type("Other") == "parallel"      # what the server sends old clients
    assert normalize_study_type("موازي") == "parallel"
    assert normalize_study_type("الصباحية") == "morning"
    assert normalize_study_type("") is None
    assert normalize_study_type("xyz") is None


# ── Printing: the bug where an evening student printed «الصباحية» ───────────

def test_certificate_prints_the_students_type():
    from services.certificate_context import study_type_display
    assert study_type_display("Evening") == "المسائية"
    assert study_type_display("مسائي") == "المسائية"         # «مساء» check used to miss this
    assert study_type_display("evening", is_english=True) == "Evening"
    assert study_type_display("Other") == "الموازية"
    assert study_type_display("parallel", is_english=True) == "Parallel"
    assert study_type_display(None) == "الصباحية"


# ── Migration and rollback ───────────────────────────────────────────────────

def test_migration_0006_shape():
    sql = _flat(_read("sql", "migrations", "0006_study_type_split.sql"))
    for needed in ("_bak_0006_students", "_bak_0006_orders", "_bak_0006_study_systems",
                   "study_system_aliases", "ADD COLUMN study_type", "information_schema"):
        assert needed in sql, needed
    # parallel is kept (user decision 1): ids 5 and 6 map to it
    assert re.search(r"\(\s*5\s*,\s*1\s*,\s*'parallel'\s*\)", sql)
    assert re.search(r"\(\s*6\s*,\s*2\s*,\s*'parallel'\s*\)", sql)


def test_rollback_0006_exists():
    sql = _flat(_read("sql", "fixes", "rollback_0006_study_type.sql"))
    assert "_bak_0006_study_systems" in sql
    assert "DROP COLUMN study_type" in sql
    assert "schema_migrations" in sql


# ── Stored procedures: old clients call some positionally ─────────────────────

def _params(sql: str, name: str) -> list[str]:
    m = re.search(r"PROCEDURE\s+`?" + name + r"`?\s*\((.*?)\)\s*(?:COMMENT[^\n]*\s*)?BEGIN", sql, re.S | re.I)
    assert m, name
    body = re.sub(r"--[^\n]*", "", m.group(1))
    names = []
    for p in body.split(","):
        words = [w for w in p.split() if w.upper() not in ("IN", "OUT", "INOUT")]
        if words and not words[0][0].isdigit():     # skip the "2)" of DECIMAL(5,2)
            names.append(words[0].strip("`").lower())
    return names


OLD_CLIENT_PROCS = ("InsertStudySystem", "UpdateStudySystem", "InsertGraduationOrder",
                    "UpdateGraduationOrder", "LinkStudentsToOrder", "InsertStudyRoutine", "UpdateStudyRoutine")


def test_old_client_procedures_keep_their_signature():
    try:
        before = subprocess.run(["git", "show", "origin/main:sql/SP.sql"], cwd=ROOT, capture_output=True,
                                check=True).stdout.decode("utf-8")
    except Exception:
        import pytest
        pytest.skip("origin/main not available")
    now = _read("sql", "SP.sql")
    for name in OLD_CLIENT_PROCS:
        assert _params(now, name) == _params(before, name), name


def test_insert_update_student_take_study_type_last():
    sql = _read("sql", "SP.sql")
    for name in ("InsertStudent", "UpdateStudent"):
        assert _params(sql, name)[-1] == "p_study_type", name


def test_procedures_return_old_spelling_for_old_clients():
    sql = _read("sql", "SP.sql").replace(" ", "")
    assert sql.count("ELT(FIELD(s.study_type,'morning','evening','parallel'),'Morning','Evening','Other')") >= 3


# ── API and sync carry the type ───────────────────────────────────────────────

def test_api_student_payload_has_study_type():
    from routers.students import StudentPayload, _study_type_arg
    assert "study_type" in StudentPayload.model_fields
    assert _study_type_arg(StudentPayload.model_construct(study_type="مسائي")) == "evening"
    assert _study_type_arg(StudentPayload.model_construct(study_type=None)) is None   # old client: keep saved


def test_sync_args_end_with_study_type():
    from routers.sync import TABLE_REGISTRY
    assert TABLE_REGISTRY["students"]["sp_args"][-1] == "study_type"
    from sync_engine import _TABLE_REGISTRY
    assert _TABLE_REGISTRY["students"]["sp_args"][-1] == "study_type"
    assert "study_type" in _TABLE_REGISTRY["students"]["columns"]


def test_bulk_import_item_accepts_study_type():
    # importing the router needs the API's main.py, so read the class instead
    import ast
    tree = ast.parse(_read("certificate_manager_api", "routers", "bulk_import.py"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BulkImportStudentItem")
    fields = {n.target.id: n for n in cls.body if isinstance(n, ast.AnnAssign)}
    assert "study_type" in fields and ast.literal_eval(fields["study_type"].value) is None


def test_reports_filter_by_study_type():
    from routers.reports import GROUPS, build_where
    assert "study_type" in GROUPS
    where, params = build_where(study_type="evening")
    assert params == ["evening"] and "study_type" in where
    assert build_where(study_type="bad") == ("", [])


# ── Screens ───────────────────────────────────────────────────────────────────

SYSTEMS_BEFORE_0006 = [
    {"id": 1, "name_ar": "نظام فصلي", "period_display": "year", "study_day_type": "Morning"},
    {"id": 2, "name_ar": "نظام مقررات", "period_display": "semester", "study_day_type": "Morning"},
    {"id": 3, "name_ar": "نظام فصلي", "period_display": "year", "study_day_type": "Evening"},
    {"id": 6, "name_ar": "نظام مقررات", "period_display": "semester", "study_day_type": "Other"},
]


def test_picker_ids_keep_the_morning_row_and_read_old_ids():
    from nicegui_ui.study_system_choice import system_ids
    base, by_id = system_ids(SYSTEMS_BEFORE_0006)
    assert sorted(base.values()) == [1, 2]
    assert by_id[3][1] == "evening" and by_id[6][1] == "parallel"
    assert base[by_id[3][0]] == 1 and base[by_id[6][0]] == 2


def test_issued_list_reads_the_students_type():
    from nicegui_screens.issued_certificates_screen import _row_study_type
    assert _row_study_type({"study_type": "evening", "study_day_type": "Morning"}) == "evening"
    assert _row_study_type({"study_day_type": "Other"}) == "parallel"
    assert _row_study_type({}) is None
