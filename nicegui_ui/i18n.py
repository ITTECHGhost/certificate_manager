# =============================================================================
# nicegui_ui/i18n.py — Interface language: العربية (default) or English
#
# One string table (i18n_table.EN, keyed by the Arabic text the screens
# write) and one function, t(text). Screens keep writing Arabic; install()
# hooks NiceGUI so that, with English chosen, every label, button, field,
# select option, table header, tab and toast is sent to the browser in
# English, and the layout becomes LTR. The two languages are never shown
# side by side.
#
# The choice is a per-PC setting stored in <data>/config/ui_language.json
# (no database column holds it, so nothing in MySQL changes).
# =============================================================================

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

log = logging.getLogger(__name__)

LANGUAGES: dict[str, str] = {"ar": "العربية", "en": "English"}
DEFAULT_LANGUAGE = "ar"

_AR = re.compile(r"[؀-ۿ]")
_state = {"lang": None}


# ── Stored choice ───────────────────────────────────────────────────────────

def _config_path():
    import app_paths
    return app_paths.data_path("config", "ui_language.json")


def get_language() -> str:
    if _state["lang"] is None:
        lang = DEFAULT_LANGUAGE
        try:
            with open(_config_path(), encoding="utf-8") as f:
                lang = str(json.load(f).get("language") or DEFAULT_LANGUAGE)
        except Exception:
            pass
        _state["lang"] = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return _state["lang"]


def set_language(lang: str, persist: bool = True) -> str:
    lang = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    _state["lang"] = lang
    translate.cache_clear()
    if persist:
        try:
            p = _config_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"language": lang}, f)
        except Exception as exc:
            log.warning("Could not save the interface language: %s", exc)
    return lang


def is_english() -> bool:
    return get_language() == "en"


def is_rtl() -> bool:
    return not is_english()


# ── Lookup ──────────────────────────────────────────────────────────────────

def _table() -> dict[str, str]:
    from nicegui_ui.i18n_table import EN
    return EN


@lru_cache(maxsize=1)
def _templates() -> list[tuple[re.Pattern, str]]:
    """Keys with '{}' become regexes; the captured values are put into the English text."""
    out = []
    for ar, en in _table().items():
        if "{}" in ar and ar.replace("{}", "").strip():
            pattern = "^" + "(.*?)".join(re.escape(p) for p in ar.split("{}")) + "$"
            out.append((re.compile(pattern, re.S), en))
    # Longest literal first, so the most specific template wins
    out.sort(key=lambda pe: -len(pe[0].pattern))
    return out


_SEPARATORS = (" — ", " • ", " · ", " | ", ": ", " - ", "\n")


@lru_cache(maxsize=8192)
def translate(text: str) -> str:
    """English for an Arabic interface string; unknown text is returned unchanged."""
    if not text or not _AR.search(text):
        return text
    table = _table()
    hit = table.get(text)
    if hit is not None:
        return hit
    stripped = text.strip()
    if stripped != text:
        hit = table.get(stripped)
        if hit is not None:
            return text.replace(stripped, hit)
    for rx, en in _templates():
        m = rx.match(stripped)
        if m:
            vals = iter(translate(v) for v in m.groups())
            return re.sub(r"\{\}", lambda _m: next(vals), en)
    # A label built from known parts ("المرحلة 1 • 2020-2021")
    for sep in _SEPARATORS:
        if sep in stripped:
            parts = stripped.split(sep)
            done = [translate(p) for p in parts]
            if done != parts:
                return sep.join(done)
    return text


def t(text: str) -> str:
    """The interface text in the chosen language (Arabic is the source)."""
    return translate(text) if is_english() else text


# ── NiceGUI hook ────────────────────────────────────────────────────────────

_TEXT_PROPS = ("label", "placeholder", "hint", "error-message", "title", "caption", "prefix", "suffix",
               "no-data-label", "no-results-label", "loading-label", "header", "message", "aria-label")


def _translate_props(props: dict) -> dict:
    out = None
    for key in _TEXT_PROPS:
        val = props.get(key)
        if isinstance(val, str) and _AR.search(val):
            out = out or dict(props)
            out[key] = translate(val)
    opts = props.get("options")
    if isinstance(opts, list) and any(isinstance(o, dict) and isinstance(o.get("label"), str) and _AR.search(o["label"]) for o in opts):
        out = out or dict(props)
        out["options"] = [
            {**o, "label": translate(o["label"])} if isinstance(o, dict) and isinstance(o.get("label"), str) else o
            for o in opts
        ]
    # A select sends its chosen option(s) as {value, label} in model-value
    for key in ("model-value", "value"):
        mv = props.get(key)
        if isinstance(mv, dict) and isinstance(mv.get("label"), str) and _AR.search(mv["label"]):
            out = out or dict(props)
            out[key] = {**mv, "label": translate(mv["label"])}
        elif isinstance(mv, list) and any(isinstance(o, dict) and isinstance(o.get("label"), str) for o in mv):
            out = out or dict(props)
            out[key] = [
                {**o, "label": translate(o["label"])} if isinstance(o, dict) and isinstance(o.get("label"), str) else o
                for o in mv
            ]
    cols = props.get("columns")
    if isinstance(cols, list) and any(isinstance(c, dict) and isinstance(c.get("label"), str) and _AR.search(c["label"]) for c in cols):
        out = out or dict(props)
        out["columns"] = [
            {**c, "label": translate(c["label"])} if isinstance(c, dict) and isinstance(c.get("label"), str) else c
            for c in cols
        ]
    return out if out is not None else props


def install() -> None:
    """Hook NiceGUI once: element text/props and ui.notify go through translate() when English is chosen."""
    from nicegui import ui
    from nicegui.element import Element

    if getattr(Element, "_i18n_installed", False):
        return
    original_to_dict = Element._to_dict

    def _to_dict(self):
        d = original_to_dict(self)
        if not is_english():
            return d
        txt = d.get("text")
        if isinstance(txt, str) and _AR.search(txt):
            d["text"] = translate(txt)
        props = d.get("props")
        if props:
            d["props"] = _translate_props(props)
        return d

    Element._to_dict = _to_dict
    Element._i18n_installed = True

    original_notify = ui.notify

    def notify(message, *args, **kwargs):
        if is_english():
            if isinstance(message, str):
                message = translate(message)
            for key in ("caption", "title"):
                if isinstance(kwargs.get(key), str):
                    kwargs[key] = translate(kwargs[key])
        return original_notify(message, *args, **kwargs)

    ui.notify = notify
