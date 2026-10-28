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
