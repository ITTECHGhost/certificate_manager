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


def test_order_not_in_system_will_be_created_first():
    res = _build()
    assert soi.missing_orders(res) == [] and [o["رقم الأمر"] for o in soi.new_orders(res)] == ["3/12/45"]


def test_order_without_date_cannot_be_created():
    rows = soi.read_csv_text(CSV.replace("2024-07-01", ""), "o.csv")
    res = soi.build(rows, STUDENTS, DEPTS, GOVS, COUNTRIES, orders=[])
    assert [o["رقم الأمر"] for o in soi.missing_orders(res)] == ["3/12/45"] and soi.new_orders(res) == []


def test_order_fields_from_the_paper():
    f = soi.order_fields({"order_date": "١/٧/٢٠٢٤", "semester": "الدور الثاني", "graduation_year": "2023-2024"})
    assert f == {"order_date": "2024-07-01", "order_semester": "second", "order_year": 2023}
    # no year on the paper: from the date (graduating 2026 = the 2025/2026 class)
    assert soi.order_fields({"order_date": "2026-07-20", "semester": ""})["order_year"] == 2025
    assert soi.order_fields({"order_date": "", "semester": "الأول"})["order_date"] is None


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


def test_payload_carries_order_fields():
    p = soi.payloads(_build().items)
    assert p[0]["order_date"] == "2024-07-01" and p[0]["order_semester"] == "first" and p[0]["order_year"] == 2023


class _Cur:
    def __init__(self, conn):
        self.conn, self.rowcount, self.lastrowid = conn, 1, 0

    def execute(self, sql, params=None):
        self.conn.sql.append(sql)
        self.conn.next_id += 1
        self.lastrowid = self.conn.next_id
        self.last = sql
        self.conn.orders_made += sql.lstrip().startswith("INSERT INTO graduation_orders")

    def fetchone(self):
        if "FROM graduation_orders" in self.last and self.conn.orders_made:
            return {"id": 77, "order_date": "2024-07-01", "graduation_semester": "first", "graduation_year": 2023}
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _Conn:
    def __init__(self):
        self.sql, self.next_id, self.orders_made, self.commits, self.rollbacks = [], 100, 0, 0, 0

    def cursor(self, **k):
        return _Cur(self)

    def start_transaction(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_server_creates_missing_order_once_then_links_every_student(monkeypatch):
    import importlib
    import types
    sys.path.append(str(ROOT / "certificate_manager_api"))
    monkeypatch.setitem(sys.modules, "main", types.SimpleNamespace(get_db=lambda: None))
    monkeypatch.delitem(sys.modules, "routers.bulk_import", raising=False)
    bi = importlib.import_module("routers.bulk_import")
    items = [bi.BulkImportStudentItem(**{k: v for k, v in x.items() if v is not None})
             for x in soi.payloads(_build().items[:2])]
    conn = _Conn()
    out = bi.bulk_import_students(bi.BulkImportRequest(students=items), conn=conn)
    assert conn.orders_made == 1 and conn.commits == 1 and conn.rollbacks == 0
    assert out["created_orders"] == ["3/12/45"] and out["linked_to_orders"] == 2
    assert list(out["order_ids"].values()) and not out["order_warnings"]
