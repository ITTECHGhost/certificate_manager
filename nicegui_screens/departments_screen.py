import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import DepartmentRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)

class DepartmentsScreen:
    """
    Departments Management Screen (NiceGUI version).
    Replicates the legacy SidePanel + RecordList layout.
    """

    def __init__(self):
        self.repo = DepartmentRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""
        
        # Side Panel state
        self.is_panel_open = False
        self.panel_mode = "add"
        self.editing_row = None

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.show_view()

    def show_view(self):
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col w-full h-full"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("business", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إدارة الأقسام — Departments").classes("text-xl font-bold app-text-primary")
                            ui.label("إدارة الأقسام والكليات في النظام").classes("text-xs app-text-muted")

                    UI.success_button(
                        "+ إضافة قسم / Add Department",
                        icon="add",
                        on_click=self.open_add_panel
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap shrink-0"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-[300px]"):
                        def on_search_change(e):
                            val = extract_event_value(e, default="")
                            self.search_term = str(val or "").strip().lower()
                            self.current_offset = 0
                            self._render_content()

                        UI.text_input(
                            label="",
                            placeholder="بحث باسم القسم أو الكلية... / Search by name or college...",
                            on_change=on_search_change
                        ).classes("flex-1 text-sm")

                    with ui.row().classes("items-center gap-2 shrink-0"):
                        ui.label("عرض / Show:").classes("text-xs font-bold app-text-muted")

                        def on_limit_change(e):
                            val = extract_event_value(e, default=25)
                            try:
                                self.current_limit = int(val or 25)
                            except Exception:
                                self.current_limit = 25
                            self.current_offset = 0
                            self._render_content()

                        UI.select(
                            label="",
                            options={25: "25", 50: "50", 75: "75", 100: "100"},
                            value=self.current_limit,
                            on_change=on_limit_change
                        ).classes("w-24 text-sm")

                # Main Body: Split Row (Left: Table, Right: Side Panel)
                @ui.refreshable
                def main_body_view():
                    with ui.row().classes("w-full flex-1 gap-6 items-start flex-nowrap overflow-hidden min-h-0"):
                        # Table Section (Flex-1)
                        with ui.column().classes("flex-1 h-full gap-4 overflow-hidden min-w-0"):
                            self._build_table()

                        # Side Panel Section (Right Side, Fixed Width when open)
                        if self.is_panel_open:
                            with ui.column().classes("w-[380px] shrink-0 h-full overflow-y-auto"):
                                self._build_side_panel()

                main_body_view()
                self._refresh_content = main_body_view

    def _render_content(self):
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def open_add_panel(self):
        self.is_panel_open = True
        self.panel_mode = "add"
        self.editing_row = None
        self._render_content()

    def open_edit_panel(self, row: dict):
        self.is_panel_open = True
        self.panel_mode = "edit"
        self.editing_row = row
        self._render_content()

    def close_panel(self):
        self.is_panel_open = False
        self.editing_row = None
        self._render_content()

    def _get_filtered_data(self) -> list[dict]:
        try:
            # DepartmentRepository.get_all() takes no parameters
            rows = self.repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch departments: {err}")
            rows = []

        if not self.search_term:
            return rows

        t = self.search_term
        filtered = [
            r for r in rows
            if t in str(r.get("name_ar") or "").lower()
            or t in str(r.get("name_en") or "").lower()
            or t in str(r.get("college_name_ar") or r.get("college_ar") or "").lower()
            or t in str(r.get("college_name_en") or r.get("college_en") or "").lower()
        ]
        return filtered

    def _build_table(self):
        all_rows = self._get_filtered_data()
        total_count = len(all_rows)
        
        start_idx = self.current_offset
        end_idx = start_idx + self.current_limit
        page_rows = all_rows[start_idx:end_idx]

        with ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[300px]"):
            if not page_rows:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("domain_disabled", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أقسام مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching departments found.").classes("text-xs app-text-muted")
            else:
                for row in page_rows:
                    self._render_card(row)

        disp_start = start_idx + 1 if total_count > 0 else 0
        disp_end = min(end_idx, total_count)

        with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
            prev_btn = UI.secondary_button("◄ السابق / Previous", on_click=self.go_prev).classes("text-xs px-4 py-2")
            if self.current_offset == 0 or self.search_term:
                prev_btn.disable()

            ui.label(f"السجلات {disp_start} - {disp_end} من {total_count}  |  Records {disp_start} - {disp_end} of {total_count}").classes("text-xs font-bold app-text-primary")

            next_btn = UI.secondary_button("التالي / Next ►", on_click=self.go_next).classes("text-xs px-4 py-2")
            if end_idx >= total_count or self.search_term:
                next_btn.disable()

    def _render_card(self, row: dict):
        col_ar = row.get("college_name_ar") or row.get("college_ar") or "—"
        
        is_selected = (self.is_panel_open and self.editing_row and self.editing_row.get("id") == row.get("id"))
        border_cls = "border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]" if is_selected else "border-[var(--border-default)]"

        with ui.row().classes(f"w-full items-center justify-between p-4 rounded-xl bg-[var(--bg-card)] border {border_cls} gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("business", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(row.get("name_ar") or "—").classes("font-bold text-base app-text-primary truncate")
                    ui.label(row.get("name_en") or "—").classes("text-xs text-slate-400 font-mono truncate")

            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("الكلية / College").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(col_ar).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent truncate max-w-[180px]")

            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                UI.primary_button(
                    "تعديل / Edit",
                    icon="edit",
                    on_click=lambda r=row: self.open_edit_panel(r)
                ).classes("text-xs px-3 py-1.5")

                UI.danger_button(
                    "حذف / Delete",
                    icon="delete",
                    on_click=lambda r=row: self.confirm_delete(r)
                ).classes("text-xs px-3 py-1.5")

    def go_prev(self):
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self._render_content()

    def go_next(self):
        self.current_offset += self.current_limit
        self._render_content()

    def _build_side_panel(self):
        """Side panel form for Add / Edit matching the legacy SidePanel behavior."""
        existing_data = self.editing_row or {}
        did = existing_data.get("id")
        mode = self.panel_mode

        with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] flex-col shadow-lg"):
            # Header
            with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)]"):
                title_ar = "إضافة قسم جديد" if mode == "add" else "تعديل قسم"
                title_en = "Add Department" if mode == "add" else "Edit Department"
                with ui.column().classes("gap-0"):
                    ui.label(f"{title_ar} — {title_en}").classes("text-base font-bold app-text-accent")
                ui.button(icon="close", on_click=self.close_panel).props("flat round dense").classes("app-text-muted")

            # Form Fields
            with ui.column().classes("w-full gap-4 py-2"):
                ui.label("معلومات القسم — Department Info").classes("text-xs font-bold app-text-muted")

                name_ar_inp = UI.text_input(
                    "اسم القسم بالعربية / Arabic Name",
                    value=existing_data.get("name_ar", "")
                ).classes("w-full text-sm")

                name_en_inp = UI.text_input(
                    "اسم القسم بالإنكليزية / English Name",
                    value=existing_data.get("name_en", "")
                ).classes("w-full text-sm")

                ui.label("معلومات الكلية — College Info").classes("text-xs font-bold app-text-muted mt-2")

                col_ar_val = existing_data.get("college_name_ar") or existing_data.get("college_ar") or ""
                col_ar_inp = UI.text_input(
                    "اسم الكلية بالعربية / Arabic College Name",
                    value=col_ar_val
                ).classes("w-full text-sm")

                col_en_val = existing_data.get("college_name_en") or existing_data.get("college_en") or ""
                col_en_inp = UI.text_input(
                    "اسم الكلية بالإنكليزية / English College Name",
                    value=col_en_val
                ).classes("w-full text-sm")

            # Action Buttons
            with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] mt-2"):
                def save_action():
                    n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                    n_en = name_en_inp.value.strip() if name_en_inp.value else ""
                    c_ar = col_ar_inp.value.strip() if col_ar_inp.value else ""
                    c_en = col_en_inp.value.strip() if col_en_inp.value else ""

                    # Full validation matching legacy SidePanel
                    if not n_ar:
                        ui.notify("اسم القسم بالعربية مطلوب  —  Arabic department name is required", type="warning")
                        return
                    if not n_en:
                        ui.notify("اسم القسم بالإنكليزية مطلوب  —  English department name is required", type="warning")
                        return
                    if not c_ar:
                        ui.notify("اسم الكلية بالعربية مطلوب  —  Arabic college name is required", type="warning")
                        return
                    if not c_en:
                        ui.notify("اسم الكلية بالإنكليزية مطلوب  —  English college name is required", type="warning")
                        return

                    payload = {
                        "name_ar": n_ar,
                        "name_en": n_en,
                        "college_ar": c_ar,
                        "college_en": c_en,
                    }

                    try:
                        if mode == "add":
                            self.repo.insert(**payload)
                            ui.notify("تمت إضافة القسم بنجاح / Department added", type="positive")
                        else:
                            self.repo.update(dept_id=did, **payload)
                            ui.notify("تم تعديل القسم بنجاح / Department updated", type="positive")
                        self.close_panel()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        log.error(f"Error saving department: {err}")
                        ui.notify(f"Error: {err}", type="negative")

                UI.secondary_button("إلغاء / Cancel", on_click=self.close_panel).classes("text-sm px-4 py-2")
                UI.success_button("💾 حفظ / Save", icon="save", on_click=save_action).classes("text-sm px-4 py-2")

    def confirm_delete(self, row: dict):
        did = row["id"]
        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد الحذف — Confirm Delete").classes("text-lg font-bold app-text-primary")
            ui.label(
                f"هل أنت متأكد من رغبتك في حذف القسم: ({row.get('name_ar', '')})؟\n"
                f"لا يمكن حذف القسم إذا كان يحتوي على طلاب أو مواد دراسية."
            ).classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_delete():
                    try:
                        self.repo.delete(did)
                        ui.notify("تم حذف القسم / Department deleted", type="positive")
                        dialog.close()
                        self._render_content()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"لا يمكن الحذف (مرتبط بطلاب/مواد). / Cannot delete: {err}", type="negative")

                UI.danger_button("حذف / Delete", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()
