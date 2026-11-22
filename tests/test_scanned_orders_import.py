"""«استيراد الأوامر الممسوحة»: CSV rows -> reviewed items -> bulk-import payload (link_only)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services import scanned_orders_import as soi  # noqa: E402

DEPTS = [{"id": 4, "name_ar": "قسم الكيمياء"}]
GOVS = [{"id": 2, "name_ar": "بغداد"}, {"id": 9, "name_ar": "البصرة"}]
COUNTRIES = [{"id": 274, "name_ar": "العراق"}]
STUDENTS = [{"id": 50, "full_name_ar": "علي حسن كاظم", "department_id": 4, "gender": 1,
             "birthplace_id": 2, "nationality_id": 274, "national_id": "199000", "study_system_id": 2,
             "date_of_birth": "2000-01-02"}]
CSV = ("order_number,order_date,department,study_type,graduation_year,semester,page,row,name_ar,"
       "gender,average,note\n"
       "3/12/45,2024-07-01,الكيمياء,صباحي,2023-2024,الدور الأول,2,1,علي حسن كاظم,,71.5,\n"
       "3/12/45,2024-07-01,الكيمياء,صباحي,2023-2024,الدور الأول,2,2,زينب احمد,أنثى,80,\n"
       "3/12/45,2024-07-01,الكيمياء,صباحي,2023-2024,الدور الأول,2,3,فلان,,500,\n")


def _build():
    rows = soi.read_csv_text(CSV, "o.csv")
    return soi.build(rows, STUDENTS, DEPTS, GOVS, COUNTRIES, orders=[])


def test_items_keep_saved_data_of_existing_student():
    it = _build().items[0]
    assert it["status"] == soi.EXACT and it["student_id"] == 50
    assert it["birthplace_id"] == 2 and it["study_system_id"] == 2 and it["national_id"] == "199000"
    assert it["average"] == 71.5 and it["study_type"] == "morning"


def test_new_student_gets_basrah_and_iraq_ids():
    it = _build().items[1]
    assert it["status"] == soi.NEW and it["student_id"] is None
    assert it["birthplace_id"] == 9 and it["nationality_id"] == 274 and it["gender"] == 2


def test_bad_average_dropped():
    assert _build().items[2]["average"] is None


def test_missing_order_reported():
    assert [o["رقم الأمر"] for o in soi.missing_orders(_build())] == ["3/12/45"]


def test_payload_is_link_only_and_keeps_system():
    p = soi.payloads(_build().items, default_system_id=1)
    assert all(x["link_only"] is True for x in p)
    assert p[0]["study_system_id"] == 2 and p[1]["study_system_id"] == 1
    assert p[0]["academic_year"] == "2023-2024" and p[0]["order_number"] == "3/12/45"


def test_server_accepts_link_only_flag():
    import ast
    tree = ast.parse((ROOT / "certificate_manager_api" / "routers" / "bulk_import.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BulkImportStudentItem")
    fields = {n.target.id: n for n in cls.body if isinstance(n, ast.AnnAssign)}
    assert ast.literal_eval(fields["link_only"].value) is False
    src = (ROOT / "certificate_manager_api" / "routers" / "bulk_import.py").read_text(encoding="utf-8")
    assert src.index("if item.link_only:") < src.index("# 2. Check or create academic periods")
