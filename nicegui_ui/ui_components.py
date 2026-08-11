# =============================================================================
# nicegui_ui/ui_components.py — Component Factory for NiceGUI
#
# All visual styling (colors, backgrounds, borders, shadows, hover states)
# is handled by CSS hook classes (app-*) defined in theme.css.
# This file contains ONLY structural Tailwind classes (sizing, padding, flex,
# grid, rounded, gaps, transitions) and CSS hook class names.
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_theme import Typography, Styles


class UI:
    """
    Component Factory providing static methods for creating pre-styled,
    theme-aware NiceGUI UI elements.

    Colors are driven entirely by CSS hook classes in theme.css.
    This file only assigns structural layout + hook class names.
    """

    # ── Containers ──────────────────────────────────────────────────────────

    @staticmethod
    def card(extra_classes: str = ""):
        """Standard card container. Colors via `.app-card` in theme.css."""
        css = f"app-card rounded-2xl p-6 gap-4 w-full {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def login_card(extra_classes: str = ""):
        """Login card container. Colors via `.app-login-card` in theme.css."""
        css = f"app-login-card login-card-glow w-[440px] max-w-full rounded-[24px] p-8 pt-10 gap-5 relative mt-8 {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def sidebar(expanded: bool = True, extra_classes: str = ""):
        """Sidebar container. Colors via `.app-sidebar` in theme.css."""
        width_cls = "w-64" if expanded else "w-20 items-center"
        css = f"app-sidebar {width_cls} h-full p-0 justify-between shrink-0 transition-all duration-300 {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def user_chip(expanded: bool = True, extra_classes: str = ""):
        """User profile chip. Colors via `.app-user-chip` in theme.css."""
        justify = "items-center gap-3" if expanded else "justify-center"
        css = f"app-user-chip w-full {justify} p-3 rounded-2xl cursor-pointer transition-all {extra_classes}".strip()
        return ui.row().classes(css)

    @staticmethod
    def header_bar(extra_classes: str = ""):
        """Top header bar. Colors via `.app-header-bar` in theme.css."""
        css = f"app-header-bar w-full h-16 px-6 flex items-center justify-between shrink-0 {extra_classes}".strip()
        return ui.row().classes(css)

    @staticmethod
    def status_badge(online: bool = True):
        """Live network status badge. Colors via `.app-status-online`/`.app-status-offline` in theme.css."""
        status_cls = "app-status-online" if online else "app-status-offline"
        dot = "🟢" if online else "🔴"
        text = "متصل / Online" if online else "غير متصل / Offline"
        return ui.label(f"{dot} {text}").classes(f"px-3 py-1.5 rounded-xl text-xs font-bold transition-colors {status_cls}")

    # ── Section Headers ─────────────────────────────────────────────────────

    @staticmethod
    def card_header(title: str, icon_name: str = "info", icon_css: str = ""):
        """Card section header. Colors via `.app-card-header` / `.app-text-*` in theme.css."""
        with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
            ui.label(title).classes(f"app-text-primary {Typography.SECTION_HEAD}")
            color = icon_css or "app-text-accent"
            ui.icon(icon_name, size="sm").classes(color)

    @staticmethod
    def section_header(title_ar: str, title_en: str = ""):
        """Bilingual page/section header. Colors via `.app-text-*` in theme.css."""
        with ui.row().classes("items-baseline gap-3"):
            ui.label(title_ar).classes("app-text-primary text-xl font-bold tracking-wide")
            if title_en:
                ui.label(f"—  {title_en}").classes("app-text-muted text-sm font-medium")

    # ── Buttons ─────────────────────────────────────────────────────────────

    @staticmethod
    def primary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Primary accent-colored button. Colors via `.app-btn-primary` in theme.css."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes(
            "app-btn-primary font-medium px-5 py-3 rounded-xl normal-case transition-all"
        )

    @staticmethod
    def secondary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Secondary button. Colors via `.app-btn-secondary` in theme.css."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes(
            "app-btn-secondary font-medium px-4 py-2 rounded-xl normal-case transition-all"
        )

    @staticmethod
    def success_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Success/emerald button. Colors via `.app-btn-success` in theme.css."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes(
            "app-btn-success font-medium px-4 py-2 rounded-xl normal-case transition-all"
        )

    @staticmethod
    def danger_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Danger/red button. Colors via `.app-btn-danger` in theme.css."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes(
            "app-btn-danger font-medium px-4 py-2 rounded-xl normal-case transition-all"
        )

    @staticmethod
    def ghost_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Transparent ghost button. Colors via `.app-btn-ghost` in theme.css."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes(
            "app-btn-ghost font-medium px-3 py-1.5 rounded-lg normal-case shadow-none transition-all"
        )

    # ── Input Fields ────────────────────────────────────────────────────────

    @staticmethod
    def input(
        label: str,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        password_toggle_button: bool = False,
        on_change = None
    ) -> ui.input:
        """Theme-aware text/password input. Colors via `.app-input` in theme.css."""
        inp = ui.input(
            label=label,
            value=value,
            placeholder=placeholder,
            password=password,
            password_toggle_button=password_toggle_button if password else False,
            on_change=on_change
        ).classes(
            "w-full app-input rounded-xl"
        ).props('outlined input-class="font-medium text-center"')
        return inp

    @staticmethod
    def text_input(label: str, value: str = "", placeholder: str = "", on_change = None) -> ui.input:
        """Alias for UI.input for standard text fields."""
        return UI.input(label=label, value=value, placeholder=placeholder, on_change=on_change)

    @staticmethod
    def select(label: str, options: list | dict, value=None) -> ui.select:
        """Theme-aware select dropdown. Colors via `.app-input` in theme.css."""
        return ui.select(label=label, options=options, value=value).classes(
            "w-full app-input rounded-xl"
        ).props("outlined")

    @staticmethod
    def number_input(label: str, value: float = 0, min=None, max=None) -> ui.number:
        """Theme-aware number input. Colors via `.app-input` in theme.css."""
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
        """Standard body text label. Color via `.app-text-primary` in theme.css."""
        return ui.label(text).classes("app-text-primary font-semibold text-sm")

    @staticmethod
    def muted_label(text: str) -> ui.label:
        """Muted secondary label. Color via `.app-text-muted` in theme.css."""
        return ui.label(text).classes("app-text-muted text-xs font-medium")

    @staticmethod
    def section_label(text: str) -> ui.label:
        """Section header label. Color via `.app-text-primary` in theme.css."""
        return ui.label(text).classes(f"app-text-primary {Typography.SECTION_HEAD}")

    # ── Complex Widgets ─────────────────────────────────────────────────────

    @staticmethod
    def stat_card(title_ar: str, title_en: str, value: int | str, icon_name: str, variant: str = "blue"):
        """Dashboard metric stat card. Colors via `.app-stat-card` in theme.css."""
        with ui.row().classes(
            "app-stat-card p-5 rounded-2xl w-full items-center flex-nowrap transition-all"
        ):
            with ui.element("div").classes(
                f"p-4 rounded-2xl border stat-icon-{variant} stat-text-{variant} shrink-0"
            ):
                ui.icon(icon_name, size="md")

            with ui.column().classes("flex-1 items-end justify-center gap-0 min-w-0"):
                ui.label(str(value)).classes(
                    "app-stat-value text-4xl font-extrabold leading-none tracking-tight"
                )
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
        """Database maintenance / action tile. Colors via `.app-tile` in theme.css."""
        variant_class = f"app-btn-{btn_variant}"
        with ui.column().classes(
            "app-tile p-4 rounded-xl gap-2 transition-all"
        ):
            ui.label(title_ar).classes("app-text-primary font-bold")
            ui.label(subtitle_ar).classes("app-text-muted text-xs")
            ui.button(btn_label, icon=btn_icon, on_click=on_click_fn, color=None).classes(
                f"{variant_class} text-xs py-2 rounded-lg normal-case mt-2 font-medium"
            )

    @staticmethod
    def quick_action_item(label_ar: str, label_en: str, icon_name: str, on_click=None):
        """Quick Action card item. Colors via `.app-action-item` in theme.css."""
        row = ui.row().classes(
            "app-action-item w-full items-center gap-3.5 px-4 py-3 rounded-xl cursor-pointer transition-all duration-200"
        )
        if on_click:
            row.on("click", on_click)
        with row:
            ui.icon(icon_name, size="sm").classes("app-sidebar-icon")
            with ui.column().classes("gap-0 min-w-0 flex-1"):
                ui.label(label_ar).classes("nav-title-ar font-bold text-sm leading-tight")
                ui.label(label_en).classes("nav-title-en font-normal text-xs leading-tight")
            ui.icon("arrow_back_ios", size="xs").classes("app-text-faint ml-auto opacity-60")
        return row

    @staticmethod
    def chip(text: str, color: str = "blue") -> ui.chip:
        """Dense chip badge with light/dark contrast."""
        return ui.chip(text, color=color).props("dense")
