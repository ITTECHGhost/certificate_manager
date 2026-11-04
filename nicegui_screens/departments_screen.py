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

        self.container = ui.column().classes("w-full gap-4")
        self.show_view()

    def show_view(self):
        self.container.clear()
        with self.container:
            with UI.card():
                with ui.row().classes("w-full items-center gap-2"):
                    def on_search_change(e):
                        val = extract_event_value(e, default="")
                        self.search_term = str(val or "").strip().lower()
                        self.current_offset = 0
                        self._render_content()

                    UI.search_input(
                        placeholder="ابحث باسم القسم أو الكلية",
                        on_change=on_search_change,
                    ).classes("flex-1 min-w-[200px] max-w-md")
                    ui.space()
                    UI.primary_button("إضافة قسم", icon="add", on_click=self.open_add_panel)

                # List, with the editor beside it when open (stacks under it on narrow windows)
                @ui.refreshable
                def main_body_view():
                    with ui.row().classes("w-full gap-6 items-start"):
                        with ui.column().classes("flex-1 gap-2 min-w-[320px]"):
                            self._build_table()

                        if self.is_panel_open:
                            with ui.column().classes("w-[360px] max-w-full shrink-0"):
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
        if not all_rows:
            if self.search_term:
                UI.empty_state("لا يوجد قسم مطابق", "تحقق من الاسم أو امسح البحث.", icon="search_off")
            else:
                UI.empty_state("لا توجد أقسام بعد", "أضف أول قسم.", icon="business",
                               action_text="إضافة قسم", on_action=self.open_add_panel)
            return

        self.current_offset = min(self.current_offset, (total_count - 1) // self.current_limit * self.current_limit)
        page_rows = all_rows[self.current_offset:self.current_offset + self.current_limit]
        rows = [{
            "id": r.get("id"),
            "name_ar": r.get("name_ar") or "—",
            "college": r.get("college_name_ar") or r.get("college_ar") or "—",
            "raw": r,
        } for r in page_rows]

        table = UI.data_table([
            {"name": "name_ar", "label": "القسم", "field": "name_ar", "align": "right"},
            {"name": "college", "label": "الكلية", "field": "college", "align": "right"},
            {"name": "actions", "label": "", "field": "actions"},
        ], rows, clickable=True)
        table.add_slot("body-cell-actions", """
            <q-td :props="props" auto-width>
                <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف القسم"
                       @click.stop="$parent.$emit('delete_dept', props.row)">
                    <q-tooltip>حذف القسم</q-tooltip>
                </q-btn>
            </q-td>
        """)
        table.on("rowClick", lambda e: self.open_edit_panel(e.args[1].get("raw")))
        table.on("delete_dept", lambda e: self.confirm_delete(e.args.get("raw") or e.args))

        UI.paginator(total_count, self.current_offset // self.current_limit + 1, self.current_limit, self._go_to_page)

    def _go_to_page(self, page: int):
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
        self._render_content()

    def _build_side_panel(self):
        """Side panel form for Add / Edit matching the legacy SidePanel behavior."""
        existing_data = self.editing_row or {}
        did = existing_data.get("id")
        mode = self.panel_mode

        with ui.column().classes("app-side-panel-card w-full gap-4"):
            # Header
            with ui.row().classes("w-full justify-between items-center no-wrap"):
                title_ar = "إضافة قسم جديد" if mode == "add" else f"تعديل القسم: {existing_data.get('name_ar', '')}"
                ui.label(title_ar).classes("app-section-title")
                UI.icon_button("close", "إغلاق", on_click=self.close_panel, dense=True)

            # Form Fields
            with ui.column().classes("w-full gap-4 py-2"):
                ui.label("معلومات القسم").classes("app-caption")

                name_ar_inp = UI.text_input(
                    "اسم القسم بالعربية",
                    value=existing_data.get("name_ar", "")
                ).classes("w-full text-sm")

                name_en_inp = UI.text_input(
                    "اسم القسم بالإنكليزية",
                    value=existing_data.get("name_en", "")
                ).classes("w-full text-sm")

                ui.label("معلومات الكلية").classes("app-caption mt-2")

                col_ar_val = existing_data.get("college_name_ar") or existing_data.get("college_ar") or ""
                col_ar_inp = UI.textarea(
                    "اسم الكلية بالعربية",
                    value=col_ar_val
                ).props("autogrow rows=1").classes("w-full")  # long college names wrap instead of clipping

                col_en_val = existing_data.get("college_name_en") or existing_data.get("college_en") or ""
                col_en_inp = UI.textarea(
                    "اسم الكلية بالإنكليزية",
                    value=col_en_val
                ).props("autogrow rows=1").classes("w-full")  # long college names wrap instead of clipping

            # Action Buttons
            with ui.row().classes("app-dialog-actions"):
                def save_action():
                    n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                    n_en = name_en_inp.value.strip() if name_en_inp.value else ""
                    c_ar = col_ar_inp.value.strip() if col_ar_inp.value else ""
                    c_en = col_en_inp.value.strip() if col_en_inp.value else ""

                    # Full validation matching legacy SidePanel
                    if not n_ar:
                        ui.notify("اسم القسم بالعربية مطلوب", type="warning")
                        return
                    if not n_en:
                        ui.notify("اسم القسم بالإنكليزية مطلوب", type="warning")
                        return
                    if not c_ar:
                        ui.notify("اسم الكلية بالعربية مطلوب", type="warning")
                        return
                    if not c_en:
                        ui.notify("اسم الكلية بالإنكليزية مطلوب", type="warning")
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
                            ui.notify("تمت إضافة القسم بنجاح", type="positive")
                        else:
                            if did is not None:
                                self.repo.update(dept_id=int(did), **payload)
                            ui.notify("تم تعديل القسم بنجاح", type="positive")
                        self.close_panel()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        log.error(f"Error saving department: {err}")
                        ui.notify(f"تعذر الحفظ: {err}", type="negative")

                UI.ghost_button("إلغاء", on_click=self.close_panel)
                UI.primary_button("حفظ", icon="save", on_click=save_action)

    def confirm_delete(self, row: dict):
        did = row["id"]
        name_ar = row.get("name_ar", "")

        def do_delete():
            try:
                self.repo.delete(did)
                UI.notify(f"تم حذف القسم ({name_ar})", type="positive")
                self._render_content()
            except OfflineModeError as err:
                UI.notify(str(err), type="warning")
            except Exception as err:
                UI.notify(f"تعذر حذف القسم: فيه طلاب أو مواد. {err}", type="negative")

        UI.confirm_dialog(
            "حذف القسم",
            f"سيُحذف القسم ({name_ar}). لا يمكن حذفه إذا كان فيه طلاب أو مواد دراسية.",
            "حذف القسم",
            do_delete,
        )
