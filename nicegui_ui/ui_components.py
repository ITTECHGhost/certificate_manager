# =============================================================================
# nicegui_ui/ui_components.py — Component Factory for NiceGUI
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_theme import Typography, Styles, get_accent_palette
from nicegui_ui.state import app_session


class UI:
    """
    Component Factory providing static methods for creating pre-styled,
    theme-aware NiceGUI UI elements with dynamic accent colors and high-contrast visibility.
    """

    # ── Theme & Accent Helpers ──────────────────────────────────────────────

    @staticmethod
    def get_accent() -> dict[str, str]:
        """Returns active theme accent palette based on session preferences."""
        accent_name = app_session.accent_color
        return get_accent_palette(accent_name)

    # ── Containers ──────────────────────────────────────────────────────────

    @staticmethod
    def card(extra_classes: str = ""):
        """
        Creates a standard card container context manager (Light/Dark mode ready).
        All screens using UI.card inherit identical border, shadow, background, and padding tokens.
        """
        css = f"{Styles.CARD} {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def login_card(extra_classes: str = ""):
        """
        Creates the specialized login card container context manager (Light/Dark mode ready).
        Inherits global card design tokens and glow effects.
        """
        css = f"{Styles.LOGIN_CARD} {extra_classes}".strip()
        return ui.column().classes(css)


    @staticmethod
    def card_header(title: str, icon_name: str = "info", icon_color: str | None = None):
        """
        Renders a card section header row with bilingual title and icon.
        Icon defaults to active accent color if not explicitly provided.
        """
        palette = UI.get_accent()
        color = icon_color or palette["primary_text"]
        with ui.row().classes("w-full justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3"):
            ui.label(title).classes(f"{Typography.SECTION_HEAD} text-slate-900 dark:text-white")
            ui.icon(icon_name, size="sm").classes(color)

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
    def primary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Primary action button styled dynamically using active accent color."""
        palette = UI.get_accent()
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            f"{palette['primary_btn']} font-medium px-5 py-3 rounded-xl normal-case transition-colors shadow-md"
        )
        return btn

    @staticmethod
    def secondary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Slate secondary button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 "
            "text-slate-800 dark:text-slate-300 font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def success_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Emerald-600 success button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def danger_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Red-600 danger button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-rose-600 hover:bg-rose-500 text-white font-medium px-4 py-2 rounded-xl normal-case transition-colors"
        )
        return btn

    @staticmethod
    def ghost_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Transparent ghost button."""
        btn = ui.button(text, icon=icon, on_click=on_click).classes(
            "bg-transparent hover:bg-slate-200 dark:hover:bg-slate-800 "
            "text-slate-700 dark:text-slate-300 font-medium px-3 py-1.5 rounded-lg normal-case shadow-none transition-colors"
        )
        return btn


    # ── Navigation & Badges ─────────────────────────────────────────────────

    @staticmethod
    def active_nav_item_classes() -> str:
        """Return CSS class string for active sidebar navigation item using active accent."""
        palette = UI.get_accent()
        return f"w-full items-center gap-3 px-3.5 py-2.5 rounded-xl border cursor-pointer transition-all {palette['active_nav']}"

    # ── Input Fields ────────────────────────────────────────────────────────

    @staticmethod
    def input(
        label: str,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        password_toggle_button: bool = False
    ) -> ui.input:
        """
        Creates a high-contrast, theme-aware text or password input field.
        Guarantees clear text, background, and border visibility across all 5 accent colors and 3 appearance modes.
        """
        inp = ui.input(
            label=label,
            value=value,
            placeholder=placeholder,
            password=password,
            password_toggle_button=password_toggle_button if password else False
        ).classes(
            "w-full bg-slate-50 dark:bg-slate-900/90 text-slate-900 dark:text-slate-100 "
            "rounded-xl transition-colors border border-slate-300 dark:border-slate-700"
        ).props('outlined input-class="text-slate-900 dark:text-slate-100 font-medium text-center"')
        return inp

    @staticmethod
    def text_input(label: str, value: str = "", placeholder: str = "") -> ui.input:
        """Alias for UI.input for standard text fields."""
        return UI.input(label=label, value=value, placeholder=placeholder)

    @staticmethod
    def select(label: str, options: list, value=None) -> ui.select:
        """Styled select dropdown with explicit dark/light mode surface contrast."""
        sel = ui.select(label=label, options=options, value=value).classes(
            "w-full bg-slate-50 dark:bg-slate-900/90 text-slate-900 dark:text-slate-100 rounded-xl"
        ).props("outlined")
        return sel

    @staticmethod
    def number_input(label: str, value: float = 0, min=None, max=None) -> ui.number:
        """Styled number input with explicit high-contrast styling."""
        num = ui.number(label=label, value=value, min=min, max=max).classes(
            "w-full bg-slate-50 dark:bg-slate-900/90 text-slate-900 dark:text-slate-100 rounded-xl"
        ).props("outlined")
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
