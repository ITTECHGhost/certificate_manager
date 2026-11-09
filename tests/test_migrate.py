import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "certificate_manager_api"))
import migrate  # noqa: E402


def test_split_handles_delimiters_quotes_and_comments():
    text = (
        "-- a comment; with a semicolon\n"
        "INSERT INTO t VALUES ('a;b', \"c;d\"); # trailing\n"
        "/* block; comment */ UPDATE t SET x = 'it''s';\n"
        "DELIMITER //\n"
        "CREATE PROCEDURE p() BEGIN SELECT 1; SELECT 2; END //\n"
        "DELIMITER ;\n"
        "SELECT 3;\n"
    )
    stmts = migrate.split_sql(text)
    assert stmts[0] == "INSERT INTO t VALUES ('a;b', \"c;d\")"
    assert stmts[1] == "UPDATE t SET x = 'it''s'"
    assert stmts[2] == "CREATE PROCEDURE p() BEGIN SELECT 1; SELECT 2; END"
    assert stmts[3] == "SELECT 3"
    assert len(stmts) == 4


def test_strip_definer():
    sql = "CREATE DEFINER=`root`@`localhost` PROCEDURE `x`() BEGIN END"
    assert migrate.strip_definer(sql) == "CREATE PROCEDURE `x`() BEGIN END"


def test_repo_sp_sql_parses_every_procedure():
    text = (ROOT / "sql" / "SP.sql").read_text(encoding="utf-8-sig")
    stmts = migrate.split_sql(migrate.strip_definer(text))
    creates = [s for s in stmts if re.match(r"CREATE\s+PROCEDURE", s, re.I)]
    assert len(creates) == len(re.findall(r"CREATE\s+DEFINER", text, re.I)) > 100
    assert all("DEFINER" not in s for s in stmts)
    assert all(re.match(r"(DROP|CREATE)\s+PROCEDURE", s, re.I) for s in stmts)


def test_plan_runs_new_and_refuses_changed(tmp_path):
    mig = tmp_path / "migrations"
    mig.mkdir()
    (mig / "0001_a.sql").write_text("SELECT 1;")
    (mig / "0002_b.sql").write_text("SELECT 2;")
    (mig / "notes.txt").write_text("ignored")
    files = migrate.migration_files(tmp_path)
    assert [p.name for p in files] == ["0001_a.sql", "0002_b.sql"]
    todo, errors = migrate.plan(files, {"0001_a.sql": migrate.sha256_of(mig / "0001_a.sql")})
    assert [p.name for p in todo] == ["0002_b.sql"] and errors == []
    todo, errors = migrate.plan(files, {"0001_a.sql": "0" * 64})
    assert errors and "0001_a.sql" in errors[0]


def test_duplicate_numbers_refused(tmp_path):
    mig = tmp_path / "migrations"
    mig.mkdir()
    (mig / "0001_a.sql").write_text("")
    (mig / "0001_b.sql").write_text("")
    with pytest.raises(SystemExit):
        migrate.migration_files(tmp_path)


def test_repo_migrations_are_well_formed():
    files = migrate.migration_files(ROOT / "sql")
    for p in files:
        body = p.read_text(encoding="utf-8-sig")
        assert not re.search(r"^\s*USE\s", body, re.I | re.M), p.name
        assert "CREATE USER" not in body.upper(), p.name
