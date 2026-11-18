import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

from routers.official_rankings import normalize_name, match_names, save_ranking, RankingPayload  # noqa: E402
from services.official_ranking_import import parse_rows  # noqa: E402
from data.repositories.official_rankings import pick_official_rank  # noqa: E402


def test_normalize_folds_spellings():
    assert normalize_name("عبد الحسين علي") == normalize_name("عبدالحسين  علي")
    assert normalize_name("أسامة") == normalize_name("اسامه")
    assert normalize_name("مُصطفى") == normalize_name("مصطفي")


def test_match_only_unique():
    students = [{"id": 1, "full_name_ar": "علي حسن"}, {"id": 2, "full_name_ar": "زيد علي"},
                {"id": 3, "full_name_ar": "زيد علي"}]
    assert match_names(["علي  حسن", "زيد علي", "مجهول"], students) == [1, None, None]


def test_parse_rows_finds_header_and_numbers():
    rows = [("كلية", None, None), ("ت", "الاسم", "المعدل"), (1, "علي حسن", "85,5"), (None, None, None),
            (2, "زيد علي", 80)]
    out = parse_rows(rows)
    assert [r["position"] for r in out] == [1, 2]
    assert out[0]["average"] == 85.5


def test_parse_rows_rejects_duplicates_and_missing_header():
    with pytest.raises(ValueError):
        parse_rows([("ت", "الاسم"), (1, "أ"), (1, "ب")])
    with pytest.raises(ValueError):
        parse_rows([("a", "b")])


class _Cur:
    lastrowid = 7
    def execute(self, *a): pass
    def executemany(self, *a): raise RuntimeError("boom")
    def close(self): pass


class _Conn:
    committed = rolled = False
    def cursor(self, **k): return _Cur()
    def commit(self): self.committed = True
    def rollback(self): self.rolled = True


def test_save_rolls_back_everything_on_error():
    from fastapi import HTTPException
    conn = _Conn()
    p = RankingPayload(list_type="jobs", entries=[{"position": 1, "name_written": "x"}])
    with pytest.raises(HTTPException) as e:
        save_ranking(p, conn)
    assert e.value.status_code == 500 and conn.rolled and not conn.committed


def test_pick_newest_of_type():
    lists = [{"list_type": "masters", "position": 3}, {"list_type": "jobs", "position": 5},
             {"list_type": "jobs", "position": 9}]
    assert pick_official_rank(lists, "jobs")["position"] == 5
    assert pick_official_rank([], "jobs") is None


def test_migration_and_rollback_exist():
    m = (ROOT / "sql/migrations/0007_official_rankings.sql").read_text(encoding="utf-8")
    assert "official_ranking_entries" in m and "ON DELETE CASCADE" in m
    assert (ROOT / "sql/fixes/rollback_0007_official_rankings.sql").is_file()
