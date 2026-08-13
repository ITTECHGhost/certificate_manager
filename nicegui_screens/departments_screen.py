import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import DepartmentRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)

class DepartmentsScreen:
    """
    Departments Management Screen (NiceGUI version).
    Uses full page views for list and edit modes.
    """

    def __init__(self):
        self.repo = DepartmentRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.show_list_view()

    def show_list_view(self):
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("business", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إدارة الأقسام — Departments").classes("text-xl font-bold app-text-primary")
                            ui.label("إدارة الأقسام والكليات في النظام").classes("text-xs app-text-muted")

                    UI.success_button(
                        "+ إضافة قسم / Add Department",
                        icon="add",
                        on_click=lambda: self.show_edit_view(mode="add")
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
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

                @ui.refreshable
                def depts_content_view():
                    self._build_table()

                depts_content_view()
                self._refresh_content = depts_content_view

    def _render_content(self):
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def _get_filtered_data(self) -> list[dict]:
        try:
            fetch_limit = 500 if self.search_term else self.current_limit
            fetch_offset = 0 if self.search_term else self.current_offset
            rows = self.repo.get_all(limit=fetch_limit, offset=fetch_offset) or []
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
        rows = self._get_filtered_data()

        with ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[340px]"):
            if not rows:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("domain_disabled", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أقسام مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching departments found.").classes("text-xs app-text-muted")
            else:
                for row in rows:
                    self._render_card(row)

        start_idx = self.current_offset + 1 if rows else 0
        end_idx = self.current_offset + len(rows)

        with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
            prev_btn = UI.secondary_button("◄ السابق / Previous", on_click=self.go_prev).classes("text-xs px-4 py-2")
            if self.current_offset == 0 or self.search_term:
                prev_btn.disable()

            ui.label(f"السجلات {start_idx} - {end_idx}  |  Records {start_idx} - {end_idx}").classes("text-sm font-bold app-text-primary")

            next_btn = UI.secondary_button("التالي / Next ►", on_click=self.go_next).classes("text-xs px-4 py-2")
            if len(rows) < self.current_limit or self.search_term:
                next_btn.disable()

    def _render_card(self, row: dict):
        col_ar = row.get("college_name_ar") or row.get("college_ar") or "—"
        col_en = row.get("college_name_en") or row.get("college_en") or "—"

        with ui.row().classes("w-full items-center justify-between p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("business", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(row.get("name_ar") or "—").classes("font-bold text-base app-text-primary truncate")
                    ui.label(row.get("name_en") or "—").classes("text-xs text-slate-400 font-mono truncate")

            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("الكلية / College").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(col_ar).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent truncate max-w-[200px]")

            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                UI.primary_button(
                    "تعديل / Edit",
                    icon="edit",
                    on_click=lambda r=row: self.show_edit_view(row=r, mode="edit")
                ).classes("text-xs px-3 py-1.5")

                UI.danger_button(
                    "Delete / حذف",
                    icon="delete",
                    on_click=lambda r=row: self.confirm_delete(r)
                ).classes("text-xs px-3 py-1.5")

    def go_prev(self):
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self._render_content()

    def go_next(self):
        self.current_offset += self.current_limit
        self._render_content()

    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        self.container.clear()
        existing_data = row or {}
        did = existing_data.get("id")

        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col max-w-4xl mx-auto w-full"):
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.button(icon="arrow_back", on_click=self.show_list_view).props("flat round dense").classes("app-text-primary")
                        title_text = "إضافة قسم جديد — Add Department" if mode == "add" else f"تعديل القسم — Edit {existing_data.get('name_en', '')}"
                        ui.label(title_text).classes("text-xl font-bold app-text-primary")

                with ui.column().classes("w-full gap-6 overflow-y-auto"):
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)]"):
                        ui.label("معلومات القسم — Department Info").classes("text-base font-bold app-text-accent")

                        with ui.row().classes("w-full gap-4"):
                            name_ar_inp = UI.text_input(
                                "اسم القسم بالعربية / Arabic Name",
                                value=existing_data.get("name_ar", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                            name_en_inp = UI.text_input(
                                "اسم القسم بالإنكليزية / English Name",
                                value=existing_data.get("name_en", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            col_ar_val = existing_data.get("college_name_ar") or existing_data.get("college_ar") or ""
                            col_ar_inp = UI.text_input(
                                "اسم الكلية بالعربية / Arabic College Name",
                                value=col_ar_val
                            ).classes("flex-1 text-sm")

                            col_en_val = existing_data.get("college_name_en") or existing_data.get("college_en") or ""
                            col_en_inp = UI.text_input(
                                "اسم الكلية بالإنكليزية / English College Name",
                                value=col_en_val
                            ).classes("flex-1 text-sm")

                        with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)]"):
                            def save_action():
                                n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                                n_en = name_en_inp.value.strip() if name_en_inp.value else ""
                                c_ar = col_ar_inp.value.strip() if col_ar_inp.value else ""
                                c_en = col_en_inp.value.strip() if col_en_inp.value else ""

                                if not n_ar:
                                    ui.notify("اسم القسم بالعربية مطلوب / Arabic name is required", type="warning")
                                    return
                                if not n_en:
                                    ui.notify("اسم القسم بالإنكليزية مطلوب / English name is required", type="warning")
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
                                        ui.notify("تمت الإضافة بنجاح / Department added", type="positive")
                                    else:
                                        self.repo.update(dept_id=did, **payload)
                                        ui.notify("تم التعديل بنجاح / Department updated", type="positive")
                                    self.show_list_view()
                                except OfflineModeError as err:
                                    ui.notify(str(err), type="warning")
                                except Exception as err:
                                    log.error(f"Error saving department: {err}")
                                    ui.notify(f"Error: {err}", type="negative")

                            UI.secondary_button("إلغاء / Cancel", on_click=self.show_list_view).classes("text-sm px-5 py-2")
                            UI.success_button("💾 حفظ / Save", icon="save", on_click=save_action).classes("text-sm px-5 py-2")

    def confirm_delete(self, row: dict):
        did = row["id"]
        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد الحذف — Confirm Delete").classes("text-lg font-bold app-text-primary")
            ui.label(
                f"هل أنت تأكد من رغبتك في حذف القسم: ({row.get('name_ar', '')})؟\n"
                f"لا يمكن حذف القسم إذا كان يحتوي على طلاب أو مواد دراسية."
            ).classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_delete():
                    try:
                        self.repo.delete(did)
                        ui.notify("تم حذف القسم / Department deleted", type="positive")
                        dialog.close()
                        self.show_list_view()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"لا يمكن الحذف (مرتبط بطلاب/مواد). / Cannot delete: {err}", type="negative")

                UI.danger_button("حذف / Delete", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()
