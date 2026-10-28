"""data.repositories as a package: module-level state other code touches through the package stays live."""
import sys

import data.repositories as repos


def _owner():
    """The module whose globals RoleRepository actually reads."""
    return sys.modules[repos.RoleRepository.__module__]


def test_sync_style_reset_clears_the_role_repository_cache(monkeypatch):
    owner = _owner()
    monkeypatch.setattr(owner, "_USER_ROLE_CACHE", {"1": "admin"})
    repos._USER_ROLE_CACHE = None  # what sync_engine.pull_mysql_to_sqlite does after an inbound sync
    assert owner._USER_ROLE_CACHE is None


def test_package_reads_the_live_role_state(monkeypatch):
    owner = _owner()
    monkeypatch.setattr(owner, "_USER_ROLE_CACHE", {"7": "registrar"})
    monkeypatch.setattr(owner, "_ROLES_INITIALIZED", True)
    assert repos._USER_ROLE_CACHE == {"7": "registrar"}
    assert repos._ROLES_INITIALIZED is True
