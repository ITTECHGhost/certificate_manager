# =============================================================================
# nicegui_ui/ui_components.py — Component Factory for NiceGUI
#
# All visual styling is inherited from CSS hook classes (app-*) defined in
# theme.css. Component methods accept structural layout overrides only
# (width, padding, extra_classes, etc.).
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_theme import Typography, Styles


class UI:
    """
    Component Factory providing static methods for creating pre-styled,
    theme-aware NiceGUI UI elements.

    Visual styling comes from CSS classes in theme.css.
    Components accept structural layout parameters only.
    """

    # ── Containers ──────────────────────────────────────────────────────────

    @staticmethod
    def card(extra_classes: str = ""):
        """Standard card container. Visual styling from CSS `.app-card`."""
        css = f"{Styles.CARD} {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def login_card(extra_classes: str = ""):
        """Login card container. Visual styling from CSS `.app-login-card`."""
        css = f"{Styles.LOGIN_CARD} {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def card_header(title: str, icon_name: str = "info", icon_css: str = ""):
        """
        Card section header row with title and icon.
        Border from CSS `.app-card-header`. Icon color defaults to accent.
        """
        with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
            ui.label(title).classes(f"app-text-primary {Typography.SECTION_HEAD}")
            color = icon_css or "app-text-accent"
            ui.icon(icon_name, size="sm").classes(color)

    @staticmethod
    def section_header(title_ar: str, title_en: str = ""):
        """Bilingual page/section header."""
        with ui.row().classes("items-baseline gap-3"):
            ui.label(title_ar).classes("app-text-primary text-xl font-bold tracking-wide")
            if title_en:
                ui.label(f"—  {title_en}").classes("app-text-muted text-sm font-medium")

    # ── Buttons ─────────────────────────────────────────────────────────────

    @staticmethod
    def primary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Primary accent-colored button. Visual styling from CSS `.app-btn-primary`."""
        return ui.button(text, icon=icon, on_click=on_click).classes(
            "app-btn-primary font-medium px-5 py-3 rounded-xl normal-case"
        ).props("color=none")

    @staticmethod
    def secondary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Secondary muted button. Visual styling from CSS `.app-btn-secondary`."""
        return ui.button(text, icon=icon, on_click=on_click).classes(
            "app-btn-secondary font-medium px-4 py-2 rounded-xl normal-case"
        ).props("color=none")

    @staticmethod
    def success_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Success/emerald button. Visual styling from CSS `.app-btn-success`."""
        return ui.button(text, icon=icon, on_click=on_click).classes(
            "app-btn-success font-medium px-4 py-2 rounded-xl normal-case"
        ).props("color=none")

    @staticmethod
    def danger_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Danger/red button. Visual styling from CSS `.app-btn-danger`."""
        return ui.button(text, icon=icon, on_click=on_click).classes(
            "app-btn-danger font-medium px-4 py-2 rounded-xl normal-case"
        ).props("color=none")

    @staticmethod
    def ghost_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Transparent ghost button. Visual styling from CSS `.app-btn-ghost`."""
        return ui.button(text, icon=icon, on_click=on_click).classes(
            "app-btn-ghost font-medium px-3 py-1.5 rounded-lg normal-case shadow-none"
        ).props("color=none")

    # ── Input Fields ────────────────────────────────────────────────────────

    @staticmethod
    def input(
        label: str,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        password_toggle_button: bool = False
    ) -> ui.input:
        """Theme-aware text/password input. Visual styling from CSS `.app-input`."""
        inp = ui.input(
            label=label,
            value=value,
            placeholder=placeholder,
            password=password,
            password_toggle_button=password_toggle_button if password else False
        ).classes(
            "w-full app-input rounded-xl"
        ).props('outlined input-class="font-medium text-center"')
        return inp

    @staticmethod
    def text_input(label: str, value: str = "", placeholder: str = "") -> ui.input:
        """Alias for UI.input for standard text fields."""
        return UI.input(label=label, value=value, placeholder=placeholder)

    @staticmethod
    def select(label: str, options: list, value=None) -> ui.select:
        """Theme-aware select dropdown. Visual styling from CSS `.app-input`."""
        return ui.select(label=label, options=options, value=value).classes(
            "w-full app-input rounded-xl"
        ).props("outlined")

    @staticmethod
    def number_input(label: str, value: float = 0, min=None, max=None) -> ui.number:
        """Theme-aware number input. Visual styling from CSS `.app-input`."""
        return ui.number(label=label, value=value, min=min, max=max).classes(
            "w-full app-input rounded-xl"
        ).props("outlined")

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
        """Standard body text label. Color from CSS `.app-text-primary`."""
        return ui.label(text).classes("app-text-primary font-semibold text-sm")

    @staticmethod
    def muted_label(text: str) -> ui.label:
        """Muted/secondary text label. Color from CSS `.app-text-muted`."""
        return ui.label(text).classes("app-text-muted text-xs font-medium")

    @staticmethod
    def section_label(text: str) -> ui.label:
        """Section header label. Color from CSS `.app-text-primary`."""
        return ui.label(text).classes(f"app-text-primary {Typography.SECTION_HEAD}")

    # ── Complex Widgets ─────────────────────────────────────────────────────

    @staticmethod
    def stat_card(title_ar: str, title_en: str, value: int | str, icon_name: str, variant: str = "blue"):
        """
        Dashboard metric stat card.
        Aligns icon on the left, large numbers right-aligned with bilingual subtitles.
        """
        with ui.row().classes("app-stat-card p-5 rounded-2xl border w-full items-center flex-nowrap"):
            with ui.element("div").classes(
                f"p-4 rounded-2xl border stat-icon-{variant} stat-text-{variant} shrink-0"
            ):
                ui.icon(icon_name, size="md")
                
            with ui.column().classes("flex-1 items-end justify-center gap-0 min-w-0"):
                ui.label(str(value)).classes("app-stat-value text-4xl font-extrabold leading-none tracking-tight")
                ui.element("div").classes(f"h-1 w-12 rounded-full stat-icon-{variant} mt-2 mb-1")
                ui.label(title_ar).classes("app-text-primary text-sm font-bold truncate")
                ui.label(title_en).classes("app-text-muted text-xs font-normal truncate")

    @staticmethod
    def action_tile(
        title_ar: str,
        subtitle_ar: str,
        btn_label: str,
        btn_icon: str,
        btn_variant: str = "primary",
        on_click_fn=None
    ):
        """
        Database maintenance / action tile.
        Surface from CSS `.app-tile`. Button variant from CSS `.app-btn-{variant}`.
        """
        variant_class = f"app-btn-{btn_variant}"
        with ui.column().classes("app-tile p-4 rounded-xl border gap-2"):
            ui.label(title_ar).classes("app-text-primary font-bold")
            ui.label(subtitle_ar).classes("app-text-muted text-xs")
            ui.button(btn_label, icon=btn_icon, on_click=on_click_fn).classes(
                f"{variant_class} text-xs py-2 rounded-lg normal-case mt-2"
            )

    @staticmethod
    def chip(text: str, color: str = "blue") -> ui.chip:
        """Dense chip badge."""
        return ui.chip(text, color=color).props("dense")
