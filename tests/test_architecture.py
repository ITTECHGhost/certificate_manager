from tests.check_no_direct_mysql import find_violations
from tests.helpers import API_DIR, PROJECT_ROOT


def test_client_never_talks_to_mysql():
    assert find_violations() == []


def test_password_hashing_copies_identical():
    client_copy = (PROJECT_ROOT / "utils" / "password_hashing.py").read_bytes()
    server_copy = (API_DIR / "password_hashing.py").read_bytes()
    assert client_copy == server_copy
