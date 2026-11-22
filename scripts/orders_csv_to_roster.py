"""Scanned graduation-order lists -> roster files for the students bulk import.

Input: one UTF-8 CSV per order (made by Gemini from the scans), columns
  order_number,order_date,department,study_type,graduation_year,semester,page,row,
  name_ar,gender,average,note
Output (in OUT_DIR, which must be OUTSIDE the repository - real names never go to git):
  roster_<department>.xlsx  one per department, official STUDENT_ROSTER_HEADERS, ready for
                            الطلاب -> استيراد جماعي (choose the same department there)
  review.xlsx               every CSV row with its status, a «يحتاج إكمال» list and the
                            orders found (with "exists in the system?")

The import overwrites gender, birthplace and nationality of a student it finds, and finds
students by national ID or by the EXACT Arabic name in the department. So:
  - exact name           -> linked; the saved gender/birthplace/nationality/ID are written
  - spelling variant     -> (only أ/إ/آ/ا, ة/ه, ى/ي, spaces, diacritics differ; one candidate)
                            linked the same way, the SYSTEM spelling is written
  - several candidates   -> left out, decide by hand
  - no match             -> new student with defaults (birthplace البصرة, nationality العراق,
                            gender from the paper or ذكر), listed under «يحتاج إكمال»
Reads the database through the API only (/replica/*); writes nothing to it.

Usage:  py -3 scripts\\orders_csv_to_roster.py <csv_folder> <out_folder>
"""
import csv
import io
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from services.scanned_orders_import import *  # noqa: E402,F401,F403  (logic lives there)
from services.scanned_orders_import import build, read_csv_text, review_xlsx, roster_xlsx  # noqa: E402

def check_out_dir(out_dir):
    out = Path(out_dir).resolve()
    if out == REPO or REPO in out.parents:
        raise SystemExit("[ERROR] Output folder must be OUTSIDE the repository (real names never go to git).")
    return out


def _safe_filename(text):
    return re.sub(r'[\\/:*?"<>|]+', "_", text).strip() or "department"


def _fetch(table):
    import api_client
    import api_config
    resp = api_client.get(f"{api_config.get_api_url()}/replica/{table}")
    resp.raise_for_status()
    data = resp.json()
    rows, cols = data.get("rows", data), data.get("columns")
    if cols and rows and not isinstance(rows[0], dict):
        rows = [dict(zip(cols, r)) for r in rows]
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Arabic on a cp1252 console
    except AttributeError:
        pass
    if len(argv) != 2:
        print(__doc__)
        return 2
    csv_dir, out = Path(argv[0]), check_out_dir(argv[1])
    rows = []
    for p in sorted(csv_dir.glob("*.csv")):
        rows += read_csv_text(p.read_text(encoding="utf-8-sig"), p.name)
    if not rows:
        print(f"[ERROR] No CSV rows in {csv_dir}")
        return 1
    res = build(rows, _fetch("students"), _fetch("departments"), _fetch("governorates"),
                _fetch("countries"), _fetch("graduation_orders"))
    out.mkdir(parents=True, exist_ok=True)
    for dept, drows in res.roster.items():
        (out / f"roster_{_safe_filename(dept)}.xlsx").write_bytes(roster_xlsx(drows))
        print(f"[OK] roster_{_safe_filename(dept)}.xlsx: {len(drows)} students")
    (out / "review.xlsx").write_bytes(review_xlsx(res))
    counts = {}
    for r in res.review:
        counts[r["الحالة"]] = counts.get(r["الحالة"], 0) + 1
    print("[OK] review.xlsx: " + "، ".join(f"{k}: {v}" for k, v in counts.items()))
    missing = sum(1 for o in res.orders if o["موجود في النظام"] == "لا")
    if missing:
        print(f"[WARN] {missing} order(s) not in the system yet - create them before importing (sheet «الأوامر»).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
