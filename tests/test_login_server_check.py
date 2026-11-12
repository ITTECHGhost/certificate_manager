"""Helpers behind the login screen's server check.

has_offline_login_accounts decides whether the login form is shown while the
server is unreachable; preview_api_url is the URL the connection tests use.
"""
import json
import sqlite3

import pytest

import api_config
from data import query


@pytest.fixture
def local_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    def read_one(sql, params=()):
        # Same contract as sync_engine.sqlite_read_one: errors (missing table) give None
        try:
            row = conn.execute(sql, params).fetchone()
        except sqlite3.Error:
            return None
        return dict(row) if row else None

    monkeypatch.setattr(query, "sqlite_read_one", read_one)
    return conn


def _make_personnel(conn, *rows):
    conn.execute("CREATE TABLE personnel (id INTEGER, username TEXT, password_hash TEXT, is_active INTEGER)")
    conn.executemany("INSERT INTO personnel VALUES (?, ?, ?, ?)", rows)


def test_fresh_install_has_no_offline_accounts(local_db):
    assert query.has_offline_login_accounts() is False


def test_empty_personnel_table_has_no_offline_accounts(local_db):
    _make_personnel(local_db)
    assert query.has_offline_login_accounts() is False


def test_unusable_rows_do_not_count(local_db):
    _make_personnel(
        local_db,
        (1, "admin", "hash", 0),     # inactive
        (2, "", "hash", 1),          # no username
        (3, "user", "  ", 1),        # no password hash
        (4, None, None, 1),
    )
    assert query.has_offline_login_accounts() is False


def test_synced_active_account_counts(local_db):
    _make_personnel(local_db, (1, "admin", "pbkdf2$abc", 1))
    assert query.has_offline_login_accounts() is True


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "server_config.json"
    monkeypatch.setattr(api_config, "CONFIG_FILE", path)
    return path


def test_preview_url_uses_scheme_typed_in_host(config_file):
    assert api_config.preview_api_url("https://172.50.1.100", 2030) == "https://172.50.1.100:2030"
    assert api_config.preview_api_url("http://172.50.1.100/", "2030") == "http://172.50.1.100:2030"


def test_preview_url_without_scheme_keeps_saved_scheme(config_file):
    assert api_config.preview_api_url("172.50.1.100", 2030) == "http://172.50.1.100:2030"
    config_file.write_text(json.dumps({"scheme": "https", "host": "x"}), encoding="utf-8")
    assert api_config.preview_api_url("172.50.1.100", 2030) == "https://172.50.1.100:2030"


def test_preview_url_rejects_bad_port(config_file):
    with pytest.raises(ValueError):
        api_config.preview_api_url("172.50.1.100", "abc")
