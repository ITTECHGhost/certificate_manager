"""The UI is Arabic only: no English labels, placeholders or notification text in the screens."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_FILES = sorted(
    list((ROOT / "nicegui_screens").rglob("*.py"))
    + list((ROOT / "nicegui_ui").glob("*.py"))
)

TEXT_FUNCS = {
    "label", "notify", "button", "tooltip", "input", "select", "chip", "tab", "switch",
    "checkbox", "number", "textarea", "upload", "set_text", "radio", "toggle",
    "primary_button", "secondary_button", "ghost_button", "danger_button", "success_button",
    "card_header", "section_header", "section_label", "muted_label", "standard_label",
    "text_input", "date_input", "stat_card", "page_header", "empty_state", "confirm_dialog",
}
TEXT_KW = {"label", "placeholder", "title", "text", "hint", "message", "caption", "close_button"}
# Product names and file formats stay as they are.
ALLOWED = {
    "Word", "PDF", "Excel", "CSV", "SBS", "YYYY", "MM", "DD", "PNG", "JPG", "WebP", "SVG",
    "docx", "xlsx", "sql", "Windows", "Microsoft", "Ar", "En", "Master", "cr", "Cairo", "http", "https",
}
WORD = re.compile(r"[A-Za-z]{3,}")


def _strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        yield "".join(v.value for v in node.values if isinstance(v, ast.Constant))
    elif isinstance(node, ast.BinOp):
        yield from _strings(node.left)
        yield from _strings(node.right)
    elif isinstance(node, ast.IfExp):
        yield from _strings(node.body)
        yield from _strings(node.orelse)


def _english_words(text: str) -> list[str]:
    if re.fullmatch(r"[a-z_0-9.\-]+", text):  # icon names and identifiers
        return []
    return [w for w in WORD.findall(text) if w not in ALLOWED]


def test_no_english_ui_text():
    found = []
    for path in UI_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            candidates = [node.args[0]] if name in TEXT_FUNCS and node.args else []
            candidates += [k.value for k in node.keywords if k.arg in TEXT_KW]
            for cand in candidates:
                for text in _strings(cand):
                    words = _english_words(text)
                    if words:
                        found.append(f"{path.relative_to(ROOT)}:{node.lineno}: {words}")
    assert not found, "English UI text:\n" + "\n".join(found)
