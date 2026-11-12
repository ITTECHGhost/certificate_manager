import logging
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/students_screen.py — NiceGUI Students Management Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

from nicegui import ui, run, background_tasks
from nicegui_ui.ui_components import UI
from utils.display_format import average_is_valid, format_average
from nicegui_ui.student_components import StudentProfileView, StudentFormView, CourseEnrollmentView
from nicegui_screens.student_bulk_import_view import StudentBulkImportView

from data.repositories import StudentRepository

class StudentsScreen:
    def __init__(self, on_issue_certificate=None) -> None:
        from data.repositories import RoleRepository, PersonnelRepository, DepartmentRepository
        from nicegui import app
        self.repo = StudentRepository()
        self.role_repo = RoleRepository()
        self.dept_repo = DepartmentRepository()
        self.on_issue_certificate = on_issue_certificate
        self.search_input = None
        self.table = None

        # Resolve logged-in user department restriction
        # Department scope cached at login (no network call here)
        from nicegui_ui.state import app_session
        self.user_dept_scope = app_session.get_access().get("dept_scope")
        self.user_dept_id = self.user_dept_scope[0] if self.user_dept_scope else None

        self.current_limit = 25
        self.current_offset = 0
        
        self.main_container = ui.column().classes('w-full h-full p-0 m-0 gap-0')
        
        def _on_form_back(arg=None):
            if isinstance(arg, dict):
                self.profile_view.render(arg)
            elif hasattr(self.form_view, "editing_student_data") and isinstance(self.form_view.editing_student_data, dict):
                st = self.form_view.editing_student_data
                self.form_view.editing_student_data = None
                self.profile_view.render(st)
            else:
                self.show_list_view()

        def _on_bulk_import_success():
            self.show_list_view()
            self._refresh_table()

        # Instantiate the views with callbacks
        self.form_view = StudentFormView(self.repo, self.main_container, on_back=_on_form_back, on_save_callback=self._refresh_table, user_dept_scope=self.user_dept_scope)
        self.enrollment_view = CourseEnrollmentView(self.repo, self.main_container, on_back=lambda st: self.profile_view.render(st, initial_tab="periods"))
        self.bulk_import_view = StudentBulkImportView(
            self.main_container,
            on_back_callback=self.show_list_view,
            on_success_callback=_on_bulk_import_success
        )
        self.profile_view = StudentProfileView(
            self.repo, 
            self.main_container, 
            on_back=self.show_list_view, 
            on_edit=self.form_view.render_edit,
            on_manage_courses=self.enrollment_view.render,
            on_issue_certificate=self.on_issue_certificate
        )
        
        self.show_list_view()

    def show_bulk_import_view(self) -> None:
        """Switch view to the Two-Stage Excel Bulk Ingestion View."""
        self.bulk_import_view.render()

    def show_list_view(self) -> None:
        """Students list: one toolbar row (search, import, add), the table, one paginator."""
        self.main_container.clear()
        with self.main_container:
            with UI.card().classes('flex-1'):
                with ui.row().classes("w-full items-center gap-2"):
                    self.search_input = UI.search_input(
                        placeholder="ابحث باسم الطالب",
                        on_change=self._on_input_change,
                    ).classes("flex-1 min-w-[220px] max-w-md")
                    self.search_input.on("keydown.enter", lambda: self.perform_search(reset_offset=True))

                    if self.user_dept_id:
                        dept_name = next((d.get("name_ar") for d in self.dept_repo.get_all() if d["id"] == self.user_dept_id), f"قسم {self.user_dept_id}")
                        UI.chip(dept_name, "warning").tooltip("تظهر طلاب هذا القسم فقط")

                    ui.space()
                    UI.secondary_button("استيراد من Excel", icon="upload_file", on_click=self.show_bulk_import_view)
                    UI.primary_button("إضافة طالب", icon="person_add", on_click=self.form_view.render_add)

                columns = [
                    {"name": "name_ar", "label": "الاسم", "field": "name_ar", "align": "right"},
                    {"name": "department_name_ar", "label": "القسم", "field": "department_name_ar"},
                    {"name": "graduation_year", "label": "سنة التخرج", "field": "graduation_year"},
                    {"name": "average", "label": "المعدل", "field": "average"},
                    {"name": "actions", "label": "", "field": "actions"},
                ]

                # The screen appears at once with a skeleton; rows load in the background (see perform_search)
                self.skeleton = UI.skeleton(rows=6, height=36)
                self.table = UI.data_table(columns, [], row_key="student_id", clickable=True)
                self.table.set_visibility(False)

                # Arabic name with the English one under it
                self.table.add_slot("body-cell-name_ar", """
                    <q-td :props="props">
                        <div class="flex flex-col text-right leading-tight">
                            <span class="font-semibold app-text-primary">{{ props.row.name_ar }}</span>
                            <span class="app-caption" dir="ltr">{{ props.row.name_en }}</span>
                        </div>
                    </q-td>
                """)
                self.table.add_slot("body-cell-actions", """
                    <q-td :props="props" auto-width>
                        <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف الطالب"
                               @click.stop="$parent.$emit('delete_student', props.row)">
                            <q-tooltip>حذف الطالب</q-tooltip>
                        </q-btn>
                    </q-td>
                """)
                self.table.on("rowClick", lambda e: self._on_view_profile(type("M", (), {"args": e.args[1]})()))
                self.table.on("delete_student", self._on_delete_student)

                self.empty_box = ui.column().classes("w-full")
                self.empty_box.set_visibility(False)

                @ui.refreshable
                def paginator() -> None:
                    if not self.total_count:
                        return
                    UI.paginator(self.total_count, self.current_offset // self.current_limit + 1,
                                 self.current_limit, self._go_to_page)

                self.total_count = 0
                paginator()
                self._paginator = paginator
                self.perform_search(reset_offset=False)

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
                "graduation_year": "—" if str(r.get("graduation_year") or "N/A") == "N/A" else str(r.get("graduation_year")),
                "average": format_average(r.get("average"))
                + ("" if average_is_valid(r.get("average")) else " ⚠ خطأ: أكبر من 100"),
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
        """
        Start a paginated student search. The server call runs on a worker thread, so the
        app never freezes while it waits; when several searches overlap (fast typing),
        only the newest one updates the table.
        """
        if not hasattr(self, 'table') or self.table is None or getattr(self.table, 'is_deleted', False):
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

        self._search_seq = getattr(self, "_search_seq", 0) + 1
        background_tasks.create(
            self._run_search(self._search_seq, search_term, self.current_limit, self.current_offset),
            name="students-search",
        )

    async def _run_search(self, seq: int, search_term: str, limit: int, offset: int) -> None:
        try:
            raw_results = await run.io_bound(
                self.repo.search_students_paginated,
                query=search_term,
                limit=limit,
                offset=offset,
                dept_id=self.user_dept_id
            )
            mapped = self._map_rows(raw_results)
        except Exception as exc:
            log.warning(f"[StudentsScreen] Search error: {exc}")
            mapped = []
        try:
            total = await run.io_bound(self.repo.count, name_query=search_term, dept_id=self.user_dept_id)
        except Exception as exc:
            log.warning(f"[StudentsScreen] Count error: {exc}")
            total = 0
        if seq != self._search_seq:
            return  # a newer search was started while this one was running
        if not hasattr(self, 'table') or self.table is None or getattr(self.table, 'is_deleted', False):
            return
        # The count may lag the rows (offline replica, paging past the end): never show fewer than we have
        self.total_count = max(int(total or 0), offset + len(mapped))
        self.table.rows = mapped
        self.table.update()
        self.skeleton.set_visibility(False)
        self.table.set_visibility(bool(mapped))
        self._render_empty(search_term, bool(mapped))
        self._paginator.refresh()

    def _render_empty(self, search_term: str, has_rows: bool) -> None:
        self.empty_box.clear()
        self.empty_box.set_visibility(not has_rows)
        if has_rows:
            return
        with self.empty_box:
            if search_term:
                UI.empty_state("لا يوجد طالب بهذا الاسم", "تحقق من الاسم أو امسح البحث.", icon="search_off")
            else:
                UI.empty_state("لا يوجد طلاب بعد", "أضف طالبًا أو استورد قائمة من Excel.", icon="people",
                               action_text="إضافة طالب", on_action=self.form_view.render_add)

    def _go_to_page(self, page: int) -> None:
        """The paginator asks for a page number (1-based)."""
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
        self.perform_search(reset_offset=False)

    def _on_view_profile(self, msg) -> None:
        """Row click opens the student's own page."""
        row_data = getattr(msg, "args", {}) or {}
        self.profile_view.render(row_data)

    def _on_delete_student(self, msg) -> None:
        """Quiet delete icon in the row; always confirmed with the student's name."""
        row_data = getattr(msg, "args", {}) or {}
        if not isinstance(row_data, dict):
            return

        student_id = row_data.get("id") or row_data.get("student_id")
        name_ar = row_data.get("name_ar") or row_data.get("full_name_ar") or ""

        if not student_id:
            return

        def do_delete():
            try:
                self.repo.delete(student_id)
                UI.notify(f"تم حذف الطالب ({name_ar})", type="positive")
                self.perform_search(reset_offset=False)
            except Exception as err:
                log.error(f"Failed to delete student {student_id}: {err}")
                UI.notify(f"تعذر حذف الطالب: {err}", type="negative")

        UI.confirm_dialog(
            "حذف الطالب",
            f"سيُحذف الطالب ({name_ar}) مع كل مراحله ودرجاته. لا يمكن التراجع عن ذلك.",
            "حذف الطالب",
            do_delete,
        )

    def _refresh_table(self):
        """Callback to reload table data after form save."""
        if not hasattr(self, 'table') or self.table is None or getattr(self.table, 'is_deleted', False):
            return
        self.perform_search(reset_offset=True)
