# =============================================================================
# ui_components.py — Bootstrap-like Component Factory for NiceGUI
# =============================================================================
#
# Provides a unified, standardized UI factory class (`UI`) that wraps NiceGUI
# components with our theme tokens (supporting Light and Dark modes).
#
# =============================================================================

from nicegui import ui
from ui_theme import Typography, Styles


class UI:
    """
    Component Factory providing static methods for creating pre-styled,
    theme-aware NiceGUI UI elements.
    """

    # ── Containers ──────────────────────────────────────────────────────────

    @staticmethod
    def card(extra_classes: str = ""):
        """
        Creates a standard card container context manager (Light/Dark mode ready).
        """
        css = f"{Styles.SETTINGS_CARD} {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def card_header(title: str, icon_name: str = "info", icon_color: str = "text-blue-600 dark:text-blue-400"):
        """
        Renders a card section header row with bilingual title and icon.
        """
        with ui.row().classes("w-full justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3"):
            ui.label(title).classes(f"{Typography.SECTION_HEAD} text-slate-900 dark:text-white")
            ui.icon(icon_name, size="sm").classes(icon_color)

    @staticmethod
    def section_header(title_ar: str, title_en: str = ""):
        """
        Renders a page/section section header label pair.
        """
        with ui.row().classes("items-baseline gap-3"):
            ui.label(title_ar).classes("text-xl font-bold text-slate-900 dark:text-white tracking-wide")
            if title_en:
                ui.label(f"—  {title_en}").classes("text-sm font-medium text-slate-600 dark:text-slate-400")

    # ── Buttons ─────────────────────────────────────────────────────────────

    @staticmethod
    def primary_button(text: str, icon: str = None, on_click=None) -> ui.button:
        """Blue-600 primary action button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def secondary_button(text: str, icon: str = None, on_click=None) -> ui.button:
        """Slate secondary button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 "
            "text-slate-800 dark:text-slate-300 font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def success_button(text: str, icon: str = None, on_click=None) -> ui.button:
        """Emerald-600 success button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def danger_button(text: str, icon: str = None, on_click=None) -> ui.button:
        """Red-600 danger button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-red-600 hover:bg-red-500 text-white font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def ghost_button(text: str, icon: str = None, on_click=None) -> ui.button:
        """Transparent ghost button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-transparent hover:bg-slate-200 dark:hover:bg-slate-800 "
            "text-slate-700 dark:text-slate-300 font-medium px-3 py-1.5 rounded-lg normal-case shadow-none transition-colors"
        )
        return btn

    # ── Input Fields ────────────────────────────────────────────────────────

    @staticmethod
    def text_input(label: str, value: str = "", placeholder: str = "") -> ui.input:
        """Styled text input field."""
        inp = ui.input(label=label, value=value, placeholder=placeholder).classes("w-full").props("outlined")
        return inp

    @staticmethod
    def select(label: str, options: list, value=None) -> ui.select:
        """Styled select dropdown."""
        sel = ui.select(label=label, options=options, value=value).classes("w-full").props("outlined")
        return sel

    @staticmethod
    def number_input(label: str, value: float = 0, min=None, max=None) -> ui.number:
        """Styled number input."""
        num = ui.number(label=label, value=value, min=min, max=max).classes("w-full").props("outlined")
        return num

    @staticmethod
    def switch(label: str, value: bool = False, on_change=None) -> ui.switch:
        """Styled toggle switch."""
        sw = ui.switch(label, value=value)
        if on_change:
            sw.on("change", lambda e: on_change(e.value))
        return sw

    # ── Labels & Text ───────────────────────────────────────────────────────

    @staticmethod
    def standard_label(text: str) -> ui.label:
        """Standard text label."""
        return ui.label(text).classes("text-slate-900 dark:text-slate-200 font-semibold text-sm")

    @staticmethod
    def muted_label(text: str) -> ui.label:
        """Muted text label."""
        return ui.label(text).classes("text-slate-600 dark:text-slate-400 text-xs font-medium")

    @staticmethod
    def section_label(text: str) -> ui.label:
        """Section header label."""
        return ui.label(text).classes(f"{Typography.SECTION_HEAD} text-slate-900 dark:text-white")

    # ── Complex Widgets ─────────────────────────────────────────────────────

    @staticmethod
    def stat_card(title: str, value: int | str, icon_name: str, text_color: str, icon_bg: str):
        """
        Renders a single dashboard metric stat card.
        """
        with ui.column().classes(Styles.STAT_CARD):
            with ui.row().classes(Styles.STAT_ICON_ROW):
                with ui.element("div").classes(f"p-3 rounded-xl border {icon_bg} {text_color}"):
                    ui.icon(icon_name, size="sm")
            with ui.column().classes("gap-1"):
                ui.label(str(value)).classes(Styles.STAT_VALUE)
                ui.label(title).classes(Styles.STAT_LABEL)

    @staticmethod
    def action_tile(title_ar: str, subtitle_ar: str, btn_label: str, btn_icon: str, btn_color: str, on_click_fn):
        """
        Renders a compact database maintenance / action tile.
        """
        with ui.column().classes("p-4 bg-slate-50 dark:bg-slate-900/60 rounded-xl border border-slate-200 dark:border-slate-800 gap-2"):
            ui.label(title_ar).classes("font-bold text-slate-900 dark:text-slate-200")
            ui.label(subtitle_ar).classes("text-xs text-slate-600 dark:text-slate-400")
            ui.button(btn_label, icon=btn_icon, on_click=on_click_fn).classes(
                f"{btn_color} text-white text-xs py-2 rounded-lg normal-case mt-2"
            )

    @staticmethod
    def chip(text: str, color: str = "blue") -> ui.chip:
        """Renders a dense chip."""
        return ui.chip(text, color=color).props("dense")
