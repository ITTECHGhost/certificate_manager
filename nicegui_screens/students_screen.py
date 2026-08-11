import logging
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/students_screen.py — NiceGUI Students Management Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles
from nicegui_ui.student_components import StudentProfileView, StudentFormView

from data.repositories import StudentRepository

class StudentsScreen:
    def __init__(self) -> None:
        self.repo = StudentRepository()
        self.search_input = None
        self.table = None
        self.limit_select = None
        self.prev_btn = None
        self.next_btn = None
        self.page_info_label = None

        self.current_limit = 25
        self.current_offset = 0
        
        self.main_container = ui.column().classes('w-full h-full p-0 m-0 gap-0')
        
        # Instantiate the views with callbacks
        self.profile_view = StudentProfileView(self.repo, self.main_container, on_back=self.show_list_view)
        self.form_view = StudentFormView(self.repo, self.main_container, on_back=self.show_list_view, on_save_callback=self._refresh_table)
        
        self.show_list_view()

    def show_list_view(self) -> None:
        """Constructs the primary Students List view layout."""
        self.main_container.clear()
        with self.main_container:
            with UI.card().classes('flex-1'):
                UI.card_header("إدارة الطلاب — Students Management", "people", icon_css="stat-text-blue")

                # Top Search & Action Bar
                with ui.row().classes("w-full items-center justify-between gap-4 mt-2"):
                    with ui.row().classes("items-center gap-2 flex-1 max-w-xl"):
                        self.search_input = UI.text_input(
                            label="ابحث بالاسم (Search student by name)",
                            placeholder="أدخل اسم الطالب...",
                            on_change=self._on_input_change
                        ).classes("flex-1").props('debounce="300"')
                        self.search_input.on("keydown.enter", lambda: self.perform_search(reset_offset=True))

                        ui.button(
                            "Search / بحث",
                            icon="search",
                            on_click=lambda: self.perform_search(reset_offset=True)
                        ).props("color=primary").classes("h-12 px-4 shadow-sm")

                    ui.button(
                        "Add Student / إضافة طالب", 
                        icon="person_add", 
                        on_click=self.form_view.render_add
                    ).props("color=positive").classes("h-12 px-4 shadow-sm")

                columns = [
                    {"name": "name_ar", "label": "Name / الاسم", "field": "name_ar", "align": "right", "sortable": True},
                    {"name": "department_name_ar", "label": "Department / القسم", "field": "department_name_ar", "align": "left", "sortable": True},
                    {"name": "graduation_year", "label": "Grad Year / سنة التخرج", "field": "graduation_year", "align": "center", "sortable": True},
                    {"name": "average", "label": "Average / المعدل", "field": "average", "align": "center", "sortable": True},
                    {"name": "actions", "label": "Actions / الإجراءات", "field": "actions", "align": "center"},
                ]

                # Initial Data Fetch
                initial_data = []
                try:
                    raw_initial = self.repo.search_students_paginated(query="", limit=self.current_limit, offset=self.current_offset)
                    initial_data = self._map_rows(raw_initial)
                except Exception as e:
                    log.warning(f"Failed to fetch initial students: {e}")

                self.table = ui.table(
                    columns=columns,
                    rows=initial_data,
                    row_key="student_id"
                ).classes(Styles.TABLE_CLASSES).props("flat bordered hide-bottom")

                # Body slot for Stacked Name Display (Arabic top, English bottom)
                self.table.add_slot("body-cell-name_ar", """
                    <q-td :props="props">
                        <div class="flex flex-col text-right leading-tight">
                            <span class="font-bold text-slate-100 text-sm">{{ props.row.name_ar }}</span>
                            <span class="text-xs text-slate-400 font-mono" dir="ltr">{{ props.row.name_en }}</span>
                        </div>
                    </q-td>
                """)

                # Body slot for Actions
                self.table.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn size="sm" color="primary" label="View Profile" @click="$parent.$emit('view_profile', props.row)" />
                    </q-td>
                """)

                self.table.on("view_profile", self._on_view_profile)

                # Pagination & Rows-Per-Page Controls Footer
                with ui.row().classes("w-full items-center justify-between mt-4 px-2 py-2 border-t border-slate-700/50"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label("Rows per page / عدد الصفوف:").classes("text-sm text-slate-300 font-medium")
                        self.limit_select = ui.select(
                            options=[25, 50, 100],
                            value=self.current_limit,
                            on_change=self._on_limit_change
                        ).props("dense options-dense outlined").classes("w-24")

                    self.page_info_label = ui.label("").classes("text-sm font-semibold text-slate-300")

                    with ui.row().classes("items-center gap-2"):
                        self.prev_btn = ui.button(
                            "Previous / السابق",
                            icon="chevron_right",
                            on_click=self._prev_page
                        ).props("color=primary dense outlined")

                        self.next_btn = ui.button(
                            "Next / التالي",
                            icon="chevron_left",
                            on_click=self._next_page
                        ).props("color=primary dense outlined")

                self._update_pagination_controls(len(initial_data))

    def _map_rows(self, raw_rows) -> list[dict]:
        """Format raw database student records for ui.table compatibility."""
        results = []
        for r in (raw_rows or []):
            if not isinstance(r, dict):
                continue
            student_id = r.get("student_id") if "student_id" in r else r.get("id", 0)
            name_en = r.get("name_en") or r.get("full_name_en") or ""
            if name_en == "Unknown":
                name_en = ""
            mapped = {
                "id": student_id,
                "student_id": student_id,
                "name_ar": r.get("name_ar") or r.get("full_name_ar") or "—",
                "name_en": name_en,
                "department_name_ar": r.get("department_name_ar") or r.get("dept_name_ar") or "—",
                "graduation_year": str(r.get("graduation_year") or "—"),
                "average": round(float(r.get("average")), 3) if r.get("average") is not None and str(r.get("average")).replace('.', '', 1).isdigit() else r.get("average", "—")
            }
            results.append(mapped)
        return results

    def _on_input_change(self, event) -> None:
        """Handle typing in search box: ignore 1-char inputs, trigger on 0 or >=2 chars."""
        val = ""
        if hasattr(event, "value") and event.value is not None:
            val = str(event.value).strip()
        elif self.search_input and self.search_input.value:
            val = str(self.search_input.value).strip()

        # Do NOT trigger automatic filtering when input length is exactly 1 character
        if len(val) == 1:
            return

        self.perform_search(reset_offset=True)

    def perform_search(self, event=None, reset_offset: bool = False) -> None:
        """Execute paginated student search via 4-tier backend pipeline."""
        if self.table is None:
            return

        if reset_offset:
            self.current_offset = 0

        query = ""
        if isinstance(event, str):
            query = event
        elif self.search_input and self.search_input.value:
            query = str(self.search_input.value)

        query = query.strip()

        # If search term length is < 2, query parameter is empty string to fetch latest students ordered by ID DESC
        search_term = "" if len(query) < 2 else query

        try:
            raw_results = self.repo.search_students_paginated(
                query=search_term,
                limit=self.current_limit,
                offset=self.current_offset
            )
            mapped = self._map_rows(raw_results)
            self.table.rows = mapped
            self.table.update()
            self._update_pagination_controls(len(mapped))
        except Exception as exc:
            log.warning(f"[StudentsScreen] Search error: {exc}")
            self.table.rows = []
            self.table.update()
            self._update_pagination_controls(0)

    def _on_limit_change(self, e) -> None:
        """Handle rows-per-page dropdown selection change."""
        if e and hasattr(e, "value") and e.value:
            self.current_limit = int(e.value)
            self.current_offset = 0
            self.perform_search(reset_offset=True)

    def _prev_page(self) -> None:
        """Go to previous page."""
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self.perform_search(reset_offset=False)

    def _next_page(self) -> None:
        """Go to next page."""
        self.current_offset += self.current_limit
        self.perform_search(reset_offset=False)

    def _update_pagination_controls(self, returned_count: int) -> None:
        """Update pagination buttons and label state."""
        current_page = (self.current_offset // self.current_limit) + 1
        if self.page_info_label:
            self.page_info_label.text = f"Page / الصفحة {current_page} | Offset / الإزاحة: {self.current_offset}"

        if self.prev_btn:
            if self.current_offset == 0:
                self.prev_btn.disable()
            else:
                self.prev_btn.enable()

        if self.next_btn:
            if returned_count < self.current_limit:
                self.next_btn.disable()
            else:
                self.next_btn.enable()

    def _on_view_profile(self, msg) -> None:
        """Triggered when the View Profile button is clicked in the table slot."""
        row_data = getattr(msg, "args", {}) or {}
        self.profile_view.render(row_data)

    def _refresh_table(self):
        """Callback to reload table data after form save."""
        if self.table is None: return
        self.perform_search(reset_offset=True)
