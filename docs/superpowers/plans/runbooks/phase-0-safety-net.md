# Phase 0 — Safety net (Haiku runbook)

Goal: add a pytest suite that records today's behaviour. Later phases change code
and must keep these tests green. Nothing in the program changes in this phase.

Read `00-README.md` first. Follow its rules exactly.

## Before you start

````powershell run skip-validate
git rev-parse --show-toplevel
git branch --show-current
git branch --list refactor/install-ready
````
Expected: `F:/CR_PY/certificate_manager`. The second line must be `COLLAGE`, and the third line must be empty (no `refactor/install-ready` branch yet). Otherwise STOP.

````powershell run skip-validate
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
````
Expected: no output at all. If any line prints, STOP and ask the user to commit or stash those changes first. This includes the plan files themselves (`docs/superpowers/plans/…`, `CLAUDE.md`): they must be committed on `COLLAGE` before Phase 0 starts.

## Step 0.1 — Create the work branch

````powershell run
git switch -c refactor/install-ready
````
Expected: `Switched to a new branch 'refactor/install-ready'`

## Step 0.2 — Install pytest

````powershell run
py -3 -m pip install --disable-pip-version-check -q "pytest==9.1.1"
py -3 -m pytest --version
````
Expected: `pytest 9.1.1`

## Step 0.3 — Write `tests/__init__.py` (new file)

````python file=tests/__init__.py
# Makes `tests` a regular package, so `from tests.helpers import ...` always resolves to this folder.
````

## Step 0.4 — Write `tests/helpers.py` (new file)

````python file=tests/helpers.py
"""Shared helpers for the test suite (import as tests.helpers)."""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_DIR = PROJECT_ROOT / "certificate_manager_api"
SNAP_DIR = PROJECT_ROOT / "tests" / "snapshots"
GOLDEN_DIR = PROJECT_ROOT / "tests" / ".golden"


def run_probe(*args: str):
    """Run tests/api_probe.py in its own process inside the API folder; return its JSON result.

    The API and the client both have modules called api_config, config and db, so the
    API is never imported into the test process itself.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tests" / "api_probe.py"), *args],
        cwd=str(API_DIR), env=env, capture_output=True, text=True, encoding="utf-8", timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"api_probe failed with exit code {proc.returncode}:\n{proc.stderr[-4000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])
````

## Step 0.5 — Write `tests/conftest.py` (new file)

````python file=tests/conftest.py
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
````

## Step 0.6 — Write `pytest.ini` (new file)

````ini file=pytest.ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -q -p no:cacheprovider -m "not mysql"
markers =
    mysql: needs the local MySQL server (read-only). Run with: py -3 -m pytest -m mysql
````

## Step 0.7 — Edit `.gitignore`

**Find:**
````text edit-old=.gitignore
certificate_manager_api/logs/
````
**Replace with:**
````text edit-new=.gitignore
certificate_manager_api/logs/

# Tests (golden files hold real student data: never commit them)
tests/.golden/
.pytest_cache/
````

## Step 0.8 — Write `tests/test_architecture.py` (new file)

````python file=tests/test_architecture.py
from tests.check_no_direct_mysql import find_violations
from tests.helpers import API_DIR, PROJECT_ROOT


def test_client_never_talks_to_mysql():
    assert find_violations() == []


def test_password_hashing_copies_identical():
    client_copy = (PROJECT_ROOT / "utils" / "password_hashing.py").read_bytes()
    server_copy = (API_DIR / "password_hashing.py").read_bytes()
    assert client_copy == server_copy
````

````powershell run
py -3 -m pytest tests/test_architecture.py
````
Expected: `2 passed`

## Step 0.9 — Write `tests/api_probe.py` (new file)

````python file=tests/api_probe.py
"""Import the FastAPI app in its own process and print facts about it as ONE JSON line.

Run with the API folder as the working directory (tests/helpers.py run_probe does this):
    python tests/api_probe.py routes
    python tests/api_probe.py get /ping /departments
The app's startup event is NOT run, so nothing is written to MySQL.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())

import main  # noqa: E402  (certificate_manager_api/main.py)


def list_routes() -> list:
    from fastapi.routing import APIRoute
    found = []
    for route in main.app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods):
                found.append([method, route.path])
    return found


def get_paths(paths: list) -> dict:
    from fastapi.testclient import TestClient
    client = TestClient(main.app)  # no "with": the startup event (init_db) must not run
    result = {}
    for path in paths:
        response = client.get(path)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        result[path] = {"status": response.status_code, "json": body}
    return result


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "routes":
        output = list_routes()
    elif command == "get":
        output = get_paths(sys.argv[2:])
    else:
        raise SystemExit(f"unknown command {command}")
    print(json.dumps(output, ensure_ascii=True, default=str))
````

## Step 0.10 — Write `tests/test_api_routes.py` (new file)

````python file=tests/test_api_routes.py
import json

from tests.helpers import SNAP_DIR, run_probe

SNAPSHOT = SNAP_DIR / "api_routes.json"


def test_api_routes_unchanged_and_in_order(record_golden):
    current = run_probe("routes")
    if record_golden:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1), encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == expected
````

Record the snapshot, then check it:

````powershell run
py -3 -m pytest tests/test_api_routes.py --record-golden
(Get-Content tests/snapshots/api_routes.json -Raw | ConvertFrom-Json).Count
py -3 -m pytest tests/test_api_routes.py
````
Expected: `153`. The count line must say 153, and both pytest runs must print `1 passed`.

## Step 0.11 — Golden API responses (needs the local MySQL running)

These tests call read-only API routes in-process (no server, no port) and store the
answers in `tests/.golden/`. That folder is git-ignored because it holds student data.

Write `tests/golden_paths.txt` (new file):

````text file=tests/golden_paths.txt
# Read-only GET routes compared before/after a change (tests/test_api_golden.py).
# Not listed: /admin/backup (writes a file), /courses and /api/courses (row order changes between calls).
/ping
/health/db
/replica/tables
/students/paginated
/students/search/all
/students/search/basic
/students/count/all
/students/search/unlinked
/students/distinct/years
/students/1174
/departments
/departments/2
/study-systems
/study-systems/active
/study-systems/1
/personnel
/personnel/active
/permissions
/roles
/user-roles
/orders
/graduation-orders
/settings
/lookups/countries
/lookups/governorates
/api/dashboard/counts
/study-routines
/api/study-routines
/issued-certificates
/api/issued-certificates
/issued-certificates/latest-number
/api/issued-certificates/latest-number
/issued-certificates/report
/api/issued-certificates/report
````

Write `tests/test_api_golden.py` (new file):

````python file=tests/test_api_golden.py
import json

import pytest

from tests.helpers import GOLDEN_DIR, PROJECT_ROOT, run_probe

GOLDEN = GOLDEN_DIR / "api_get.json"
PATHS_FILE = PROJECT_ROOT / "tests" / "golden_paths.txt"


def _paths() -> list:
    lines = PATHS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.mysql
def test_get_responses_match_golden(record_golden):
    current = run_probe("get", *_paths())
    if record_golden:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert current == expected
````

````powershell run
py -3 -m pytest -m mysql --record-golden
py -3 -m pytest -m mysql
````
Expected: `1 passed`. Both runs must print `1 passed`. If the output mentions `Can't connect to MySQL`, STOP and ask the user to start MySQL (AppServ), then run this step again.

## Step 0.12 — Public names and import smoke test

Write `tests/test_public_surface.py` (new file):

````python file=tests/test_public_surface.py
"""Names other code imports from the big modules must stay importable after the refactor."""
import ast
import importlib
import json

import pytest

from tests.helpers import PROJECT_ROOT, SNAP_DIR

SNAPSHOT = SNAP_DIR / "public_names.json"
SURFACE_MODULES = [
    "data.repositories",
    "nicegui_screens.settings_screen",
    "nicegui_screens.certificate_screen",
    "nicegui_ui.student_components",
]
CLIENT_PACKAGES = ["nicegui_screens", "nicegui_ui", "services", "utils", "data"]
CLIENT_TOP_MODULES = ["sync_engine", "api_client", "api_config", "cert_repository"]
SKIP_DIRS = {"old", ".git", ".claude", ".agent", ".gemini", "tests", "build", "dist", ".venv", "certificate_manager_api"}


def _client_modules() -> list:
    names = list(CLIENT_TOP_MODULES)
    for package in CLIENT_PACKAGES:
        for path in sorted((PROJECT_ROOT / package).glob("*.py")):
            if path.stem != "__init__":
                names.append(f"{package}.{path.stem}")
    return names


def _imported_elsewhere(module_name: str) -> set:
    found = set()
    for path in PROJECT_ROOT.rglob("*.py"):
        if path.relative_to(PROJECT_ROOT).parts[0] in SKIP_DIRS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == module_name:
                found.update(alias.name for alias in node.names if alias.name != "*")
    return found


def _public_names(module_name: str) -> list:
    module = importlib.import_module(module_name)
    names = set()
    for name, obj in vars(module).items():
        if name.startswith("__"):
            continue
        owner = getattr(obj, "__module__", None)
        defined_here = callable(obj) and isinstance(owner, str) and owner.startswith(module_name)
        if defined_here or name.isupper():
            names.add(name)
    return sorted(names | _imported_elsewhere(module_name))


@pytest.mark.parametrize("module_name", SURFACE_MODULES)
def test_public_names_still_importable(module_name, record_golden):
    if record_golden:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
        data[module_name] = _public_names(module_name)
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[module_name]
    module = importlib.import_module(module_name)
    assert [name for name in expected if not hasattr(module, name)] == []


@pytest.mark.parametrize("module_name", _client_modules())
def test_client_module_imports(module_name):
    importlib.import_module(module_name)
````

````powershell run
py -3 -m pytest tests/test_public_surface.py --record-golden
py -3 -m pytest tests/test_public_surface.py
````
Expected: `38 passed`. Both runs must print `38 passed`.

## Step 0.13 — Full run

````powershell run
py -3 -m pytest
````
Expected: `41 passed, 1 deselected`

## Step 0.14 — Commit

````powershell run
git add -- .gitignore pytest.ini tests/__init__.py tests/helpers.py tests/conftest.py tests/api_probe.py tests/golden_paths.txt tests/test_architecture.py tests/test_api_routes.py tests/test_api_golden.py tests/test_public_surface.py tests/snapshots/api_routes.json tests/snapshots/public_names.json
git commit -q -m "test: add safety-net test suite (route snapshot, golden API reads, public names)"
git log --oneline -1
git status --porcelain -- tests pytest.ini .gitignore
````
Expected: `test: add safety-net test suite`. The last command must print nothing. In particular, `tests/.golden/` must not appear, because it is ignored.

## Done

Report the output of:

````powershell run
git log --oneline -3
````
Expected: `test: add safety-net test suite`
