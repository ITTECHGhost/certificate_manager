# =============================================================================
# nicegui_ui/ui_components.py — Component Factory for NiceGUI
#
# The design system in code. Colours, sizes and spacing come from the tokens
# in theme.css; this file only picks the hook classes (app-*) and structure.
# Screens build their UI from these helpers:
#
#   Buttons     primary_button · secondary_button · ghost_button · icon_button
#               danger_icon_button (quiet, red on hover)
#   Fields      input · select · number_input · date_input · switch · textarea
#   Layout      page_header · card · card_header · section_label · dl
#   Lists       data_table · paginator · search_input · empty_state · skeleton
#   Overlays    confirm_dialog · side_panel · notify (toast)
#   Flow        stepper · chip
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_theme import Typography, Styles


def _apply_component_defaults() -> None:
    """Every field is outlined and 40 px tall; every button is flat, sentence case."""
    ui.input.default_props("outlined dense")
    ui.select.default_props("outlined dense options-dense")
    ui.number.default_props("outlined dense")
    ui.textarea.default_props("outlined")
    ui.button.default_props("unelevated no-caps")


_apply_component_defaults()


class UI:
    """Static factory for the app's themed components."""

    # ── Layout ──────────────────────────────────────────────────────────────

    @staticmethod
    def page():
        """Content column of a screen: standard padding and gap, centred, max width."""
        return ui.column().classes("app-page")

    @staticmethod
    def page_header(title: str, subtitle: str = "", actions=None):
        """Section heading for a screen's main card. The page title itself lives in the top bar."""
        # Wraps: on a narrow window the actions move under the title instead of off the edge
        with ui.row().classes("w-full items-center justify-between gap-3") as row:
            with ui.column().classes("gap-0 min-w-[220px] flex-1"):
                ui.label(title).classes("app-section-title")
                if subtitle:
                    ui.label(subtitle).classes("app-caption")
            if actions:
                with ui.row().classes("items-center gap-2"):
                    actions()
        return row

    @staticmethod
    def card(extra_classes: str = ""):
        """Card container: one border, radius 8, padding 24."""
        css = f"app-card w-full max-w-full min-w-0 {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def login_card(extra_classes: str = ""):
        css = f"app-login-card w-[400px] max-w-full {extra_classes}".strip()
        return ui.column().classes(css)

    @staticmethod
    def sidebar(expanded: bool = True, extra_classes: str = ""):
        width_cls = "w-56" if expanded else "w-16 items-center"
        return ui.column().classes(f"app-sidebar {width_cls} h-full p-0 shrink-0 {extra_classes}".strip())

    @staticmethod
    def user_chip(expanded: bool = True, extra_classes: str = ""):
        return ui.row().classes(f"app-user-chip items-center no-wrap {extra_classes}".strip())

    @staticmethod
    def header_bar(extra_classes: str = ""):
        return ui.row().classes(f"{Styles.HEADER_BAR} {extra_classes}".strip())

    @staticmethod
    def card_header(title: str, icon_name: str = "", icon_css: str = ""):
        """Card section title with an optional leading icon (always the accent colour)."""
        with ui.row().classes("w-full items-center gap-2 no-wrap app-card-header"):
            if icon_name:
                ui.icon(icon_name, size="20px").classes("app-text-accent")
            ui.label(title).classes("app-section-title")

    @staticmethod
    def section_header(title_ar: str, title_en: str = ""):
        """Section title (Arabic only; the second argument is ignored)."""
        return ui.label(title_ar).classes("app-section-title")

    @staticmethod
    def section_label(text: str) -> ui.label:
        return ui.label(text).classes("app-section-title")

    @staticmethod
    def standard_label(text: str) -> ui.label:
        return ui.label(text).classes("app-text-primary font-semibold text-sm")

    @staticmethod
    def muted_label(text: str) -> ui.label:
        return ui.label(text).classes("app-caption")

    @staticmethod
    def dl(items: list[tuple[str, object]]):
        """Two-column definition list of (label, value) pairs; empty values show a dash."""
        with ui.element("div").classes("app-dl") as grid:
            for term, value in items:
                text = str(value).strip() if value not in (None, "") else "—"
                with ui.element("div").classes("app-dl-item"):
                    ui.label(term).classes("app-dl-term")
                    ui.label(text).classes("app-dl-value")
        return grid

    # ── Buttons ─────────────────────────────────────────────────────────────

    @staticmethod
    def primary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """The one filled button of a screen."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes("app-btn-primary")

    @staticmethod
    def secondary_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Outlined button for secondary actions."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes("app-btn-secondary")

    @staticmethod
    def ghost_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        """Text button for back / cancel."""
        return ui.button(text, icon=icon, on_click=on_click, color=None).props("flat").classes("app-btn-ghost")

    @staticmethod
    def back_button(on_click=None, text: str = "رجوع") -> ui.button:
        """Back: a text button with the arrow pointing the RTL 'back' way."""
        return UI.ghost_button(text, icon="arrow_forward", on_click=on_click)

    @staticmethod
    def icon_button(icon: str, tooltip: str = "", on_click=None, dense: bool = False) -> ui.button:
        """Neutral icon-only button."""
        btn = ui.button(icon=icon, on_click=on_click, color=None).props("flat round").classes("app-btn-icon")
        if dense:
            btn.props("dense")
        if tooltip:
            btn.tooltip(tooltip)
            btn.props(f'aria-label="{tooltip}"')
        return btn

    @staticmethod
    def danger_icon_button(icon: str = "delete", tooltip: str = "حذف", on_click=None, dense: bool = True) -> ui.button:
        """Destructive action, quiet: grey icon that turns red on hover. Always confirm first."""
        btn = ui.button(icon=icon, on_click=on_click, color=None).props("flat round").classes("app-btn-danger-icon")
        if dense:
            btn.props("dense")
        btn.tooltip(tooltip)
        btn.props(f'aria-label="{tooltip}"')
        return btn

    # Older names: success is the primary style; danger is the outlined red
    # button kept for confirmations and rare in-form destructive actions.
    @staticmethod
    def success_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        return UI.primary_button(text, icon=icon, on_click=on_click)

    @staticmethod
    def danger_button(text: str, icon: str | None = None, on_click=None) -> ui.button:
        return ui.button(text, icon=icon, on_click=on_click, color=None).classes("app-btn-danger")

    # ── Fields ──────────────────────────────────────────────────────────────

    @staticmethod
    def input(
        label: str,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
        password_toggle_button: bool = False,
        on_change=None,
    ) -> ui.input:
        """Text / password field, 40 px."""
        return ui.input(
            label=label,
            value=value,
            placeholder=placeholder or None,
            password=password,
            password_toggle_button=password_toggle_button if password else False,
            on_change=on_change,
        ).classes("w-full app-input")

    @staticmethod
    def text_input(label: str, value: str = "", placeholder: str = "", on_change=None) -> ui.input:
        return UI.input(label=label, value=value, placeholder=placeholder, on_change=on_change)

    @staticmethod
    def textarea(label: str, value: str = "", on_change=None) -> ui.textarea:
        return ui.textarea(label=label, value=value, on_change=on_change).classes("w-full app-input").props("autogrow")

    @staticmethod
    def search_input(placeholder: str = "بحث", on_change=None, debounce_ms: int = 300) -> ui.input:
        """Search field with a leading search icon and a clear button."""
        inp = ui.input(placeholder=placeholder, on_change=on_change).classes("w-full app-input").props(
            f"clearable debounce={debounce_ms}"
        )
        with inp.add_slot("prepend"):
            ui.icon("search").classes("app-text-faint")
        return inp

    @staticmethod
    def _normalize_on_leave(inp: ui.input, parse, error_text: str) -> ui.input:
        """On blur or Enter, rewrite the value with `parse`; show `error_text` under the field if it is invalid."""
        def _apply(_e=None):
            raw = inp.value or ""
            val = parse(raw)
            if val is None:
                inp.props(f'error error-message="{error_text}"')
                return
            inp.props(remove="error error-message")
            if val != raw:
                inp.set_value(val)
                inp.update()
        inp.on("blur", _apply)
        inp.on("keydown.enter", _apply)
        inp.on("update:model-value", lambda _e: inp.props(remove="error error-message"))
        return inp

    @staticmethod
    def attach_date_picker(inp: ui.input) -> ui.input:
        """DateField: type the date in any common form (13.10.2025, 2025/10/13, 20251013…) or pick it.

        The value becomes YYYY-MM-DD when the field loses focus or on Enter; picking a
        day in the calendar fills it and closes the calendar.
        """
        from utils.date_parsing import parse_date
        inp.props('hint="YYYY-MM-DD"')
        with inp:
            with ui.menu().props("no-parent-event") as menu:
                picker = ui.date(mask="YYYY-MM-DD")

                state = {"loading": False}

                def _picked(e):
                    # A day clicked in the calendar fills the field and closes the calendar
                    if e.value and not state["loading"]:
                        inp.value = e.value
                        inp.props(remove="error error-message")
                        menu.close()
                picker.on_value_change(_picked)

        def _open_calendar():
            state["loading"] = True
            picker.set_value(parse_date(inp.value) or None)
            state["loading"] = False
            menu.open()
        with inp.add_slot("append"):
            ui.icon("edit_calendar").on("click", _open_calendar).classes("cursor-pointer app-text-accent")
        return UI._normalize_on_leave(inp, parse_date, "تاريخ غير صالح — اكتبه مثل 2025-10-13 أو 13/10/2025")

    @staticmethod
    def attach_academic_year(inp: ui.input) -> ui.input:
        """Academic-year field: 2025, 2025-2026, 25/26… all become 2025/2026 on blur or Enter."""
        from utils.date_parsing import format_academic_year
        inp.props('hint="2025/2026"')
        return UI._normalize_on_leave(inp, format_academic_year, "سنة دراسية غير صالحة — اكتبها مثل 2025 أو 2025/2026")

    @staticmethod
    def academic_year_input(label: str, value: str = "") -> ui.input:
        from utils.date_parsing import format_academic_year
        shown = format_academic_year(value) or (value or "")
        return UI.attach_academic_year(UI.input(label=label, value=shown, placeholder="2025/2026"))

    @staticmethod
    def date_input(label: str, value: str = "", placeholder: str = "YYYY-MM-DD") -> ui.input:
        """DateField: YYYY-MM-DD with a calendar picker."""
        return UI.attach_date_picker(UI.input(label=label, value=value, placeholder=placeholder))

    @staticmethod
    def select(label: str, options: list | dict, value=None, with_input: bool = False, on_change=None) -> ui.select:
        return ui.select(options=options, label=label, value=value, with_input=with_input, on_change=on_change).classes(
            "w-full app-input"
        )

    @staticmethod
    def number_input(label: str, value: float = 0, min=None, max=None, on_change=None) -> ui.number:
        return ui.number(label=label, value=value, min=min, max=max, on_change=on_change).classes("w-full app-input")

    @staticmethod
    def switch(label: str, value: bool = False, on_change=None) -> ui.switch:
        """Switch with a clear on (green track) / off (grey track) state."""
        return ui.switch(label, value=value, on_change=on_change).props("color=primary keep-color")

    # ── Lists ───────────────────────────────────────────────────────────────

    @staticmethod
    def data_table(columns: list[dict], rows: list[dict], row_key: str = "id", clickable: bool = False) -> ui.table:
        """Table: 48 px rows, centred cells, sticky header; pagination is the shared paginator."""
        cols = []
        for col in columns:
            c = {"align": "center", "headerClasses": "", **col}
            cols.append(c)
        table = ui.table(columns=cols, rows=rows, row_key=row_key, pagination=0).classes(
            "app-table w-full" + (" app-table--clickable" if clickable else "")
        ).props("flat hide-bottom")
        return table

    @staticmethod
    def paginator(total: int, page: int, page_size: int, on_change) -> ui.row:
        """The one paginator: 'from–to of total' plus previous/next icon buttons."""
        total = max(int(total or 0), 0)
        pages = max((total + page_size - 1) // page_size, 1)
        page = min(max(int(page or 1), 1), pages)
        start = 0 if total == 0 else (page - 1) * page_size + 1
        end = min(page * page_size, total)
        with ui.row().classes("app-paginator w-full justify-between no-wrap pt-2") as row:
            ui.label(f"{start}–{end} من {total}").classes("app-caption")
            with ui.row().classes("items-center gap-1 no-wrap"):
                prev_btn = UI.icon_button("chevron_right", "السابق", on_click=lambda: on_change(page - 1))
                ui.label(f"{page} / {pages}").classes("app-caption px-2")
                next_btn = UI.icon_button("chevron_left", "التالي", on_click=lambda: on_change(page + 1))
                if page <= 1:
                    prev_btn.disable()
                if page >= pages:
                    next_btn.disable()
        return row

    @staticmethod
    def empty_state(title: str, hint: str = "", icon: str = "inbox", action_text: str = "", on_action=None):
        """Empty list: icon, one line of what's missing, and what to do next."""
        with ui.column().classes("app-empty") as col:
            ui.icon(icon)
            ui.label(title).classes("app-text-primary font-semibold")
            if hint:
                ui.label(hint).classes("app-caption")
            if action_text and on_action:
                UI.secondary_button(action_text, on_click=on_action).classes("mt-2")
        return col

    @staticmethod
    def skeleton(rows: int = 5, height: int = 40):
        """Loading placeholder shown at once while a page builds."""
        with ui.column().classes("w-full gap-3") as col:
            for _ in range(rows):
                ui.element("div").classes("app-skeleton w-full").style(f"height:{height}px")
        return col

    @staticmethod
    def chip(text: str, variant: str = "") -> ui.label:
        """Small status chip; variant: '' (neutral), 'accent', 'warning' or 'danger'."""
        cls = "app-chip" + (f" app-chip--{variant}" if variant in ("accent", "warning", "danger") else "")
        return ui.label(text).classes(cls)

    @staticmethod
    def status_badge(online: bool = True):
        return UI.chip("متصل" if online else "غير متصل", "accent" if online else "danger")

    # ── Overlays ────────────────────────────────────────────────────────────

    @staticmethod
    def confirm_dialog(title: str, message: str, confirm_text: str, on_confirm, danger: bool = True):
        """Confirmation with the item named in the message. Esc / Cancel closes; Enter confirms."""
        with ui.dialog() as dlg, ui.card().classes("app-dialog"):
            ui.label(title).classes("app-section-title")
            ui.label(message).classes("app-text-secondary text-sm")

            def _confirm():
                dlg.close()
                on_confirm()

            with ui.row().classes("app-dialog-actions"):
                UI.ghost_button("إلغاء", on_click=dlg.close)
                btn = ui.button(confirm_text, on_click=_confirm, color=None)
                btn.classes("app-btn-danger-confirm" if danger else "app-btn-primary")
                btn.props("autofocus")
        dlg.open()
        return dlg

    @staticmethod
    def side_panel():
        """Dialog that slides in from the inline-start edge, for editing one record."""
        dlg = ui.dialog().props("position=left maximized=false full-height")
        return dlg

    @staticmethod
    def stepper(steps: list[str], current: int, on_step=None):
        """Wizard header: numbered steps; finished steps are clickable to go back."""
        with ui.element("div").classes("app-stepper") as bar:
            for idx, name in enumerate(steps, start=1):
                state = "app-step--active" if idx == current else ("app-step--done" if idx < current else "")
                step = ui.element("div").classes(f"app-step {state}")
                with step:
                    ui.label("✓" if idx < current else str(idx)).classes("app-step-num")
                    ui.label(name)
                if idx < current and on_step:
                    step.on("click", lambda _e, i=idx: on_step(i))
                if idx < len(steps):
                    ui.element("div").classes("app-step-line")
        return bar

    # ── Older composite widgets (dashboard / settings) ──────────────────────

    @staticmethod
    def stat_card(title_ar: str, value: int | str, icon_name: str, variant: str = ""):
        """Metric tile: one accent colour for every icon."""
        with ui.row().classes("app-stat-card w-full items-center no-wrap") as row:
            with ui.element("div").classes("app-stat-icon"):
                ui.icon(icon_name, size="22px")
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(str(value)).classes("app-stat-value")
                ui.label(title_ar).classes("app-stat-label")
        return row

    @staticmethod
    def action_tile(
        title_ar: str,
        subtitle_ar: str,
        btn_label: str,
        btn_icon: str,
        btn_variant: str = "secondary",
        on_click_fn=None,
    ):
        """Maintenance tile: title, one line of help, one outlined action."""
        with ui.column().classes("app-tile p-4 gap-2"):
            ui.label(title_ar).classes("app-text-primary font-semibold")
            ui.label(subtitle_ar).classes("app-caption")
            UI.secondary_button(btn_label, icon=btn_icon, on_click=on_click_fn).classes("mt-2 self-start")

    @staticmethod
    def quick_action_item(label_ar: str, label_en: str, icon_name: str, on_click=None):
        row = ui.row().classes("app-nav-item w-full items-center no-wrap")
        if on_click:
            row.on("click", on_click)
        with row:
            ui.icon(icon_name, size="20px")
            ui.label(label_ar).classes("nav-title-ar")
        return row

    # ── Toast ───────────────────────────────────────────────────────────────

    @staticmethod
    def notify(message: str | Exception, type: str = "info", title: str = "", duration: float | None = None, position: str = "bottom"):
        """
        Short Arabic toast. Errors and warnings go through utils.error_formatter,
        which turns raw API / database errors into a title and what to do next.
        """
        from html import escape
        from utils.error_formatter import format_error_message

        icon_map = {"positive": "check_circle", "negative": "error_outline", "warning": "warning_amber", "info": "info"}
        norm_type = (type or "info").lower()
        norm_type = {"error": "negative", "success": "positive"}.get(norm_type, norm_type)

        if norm_type in {"negative", "warning"} or isinstance(message, Exception):
            parsed_title, parsed_desc = format_error_message(message)
            display_title = title or parsed_title
            display_msg = parsed_desc
            default_duration = 6.0
        else:
            display_title = title
            display_msg = str(message or "")
            default_duration = 3.5

        if display_title and display_msg and display_title != display_msg:
            html_content = (
                "<div style='display:flex;flex-direction:column;gap:2px;text-align:right;'>"
                f"<div style='font-weight:700;'>{escape(display_title)}</div>"
                f"<div style='opacity:.9;'>{escape(display_msg)}</div></div>"
            )
        else:
            html_content = f"<div style='font-weight:600;text-align:right;'>{escape(display_title or display_msg)}</div>"

        effective = duration if duration is not None else default_duration
        ui.notify(
            html_content,
            type=norm_type,
            icon=icon_map.get(norm_type, "info"),
            position=position,
            timeout=int(effective * 1000) if effective > 0 else 0,
            close_button="إغلاق",
            html=True,
            multi_line=True,
        )
