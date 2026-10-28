"""Test-wide setup. This runs before any project module is imported."""
import os
import tempfile

import pytest

# Every test run writes program data (logs, cache, config) into a throw-away folder.
os.environ["CERTMAN_DATA_DIR"] = tempfile.mkdtemp(prefix="cm_test_data_")


def pytest_addoption(parser):
    parser.addoption("--record-golden", action="store_true", default=False,
                     help="Write snapshot/golden files instead of only comparing against them.")


@pytest.fixture(scope="session")
def record_golden(request) -> bool:
    return bool(request.config.getoption("--record-golden"))
