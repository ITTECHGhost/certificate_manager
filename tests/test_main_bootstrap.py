"""main.py must prepare the data folder before NiceGUI or any screen is imported."""
import ast

from tests.helpers import PROJECT_ROOT

MAIN = PROJECT_ROOT / "main.py"


def _top_level_calls() -> list:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    return [ast.unparse(node.value.func) for node in tree.body
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]


def test_freeze_support_then_prepare_data_dir_come_first():
    assert _top_level_calls()[:2] == ["freeze_support", "app_paths.prepare_data_dir"]


def test_data_dir_prepared_before_nicegui_import():
    body = ast.parse(MAIN.read_text(encoding="utf-8")).body
    prepare_at = next(i for i, node in enumerate(body)
                      if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                      and ast.unparse(node.value.func) == "app_paths.prepare_data_dir")
    first_ui_import = next(i for i, node in enumerate(body)
                           if isinstance(node, (ast.Import, ast.ImportFrom))
                           and any(name in ast.unparse(node) for name in ("nicegui", "utils.logger", "nicegui_screens")))
    assert prepare_at < first_ui_import


def test_no_hardcoded_storage_secret():
    assert "certificate_manager_secret_key" not in MAIN.read_text(encoding="utf-8")
