import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import CourseRepository, DepartmentRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)

class CoursesScreen:
    """
    Courses Management Screen (NiceGUI version).
    Uses full page views for list and edit modes (view replacing UI).
    """

    def __init__(self):
        self.repo = CourseRepository()
        self.dept_repo = DepartmentRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""
        self.filter_dept = 0

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.show_list_view()

    def show_list_view(self):
        self.container.clear()
        
        try:
            depts = self.dept_repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch departments for course filter: {err}")
            depts = []
            
        self.depts_map = {d["id"]: d for d in depts}
        filter_dept_opts = {0: "كل الأقسام / All Departments"}
        for d in depts:
            filter_dept_opts[d["id"]] = f"{d.get('name_ar', '')} / {d.get('name_en', '')}"

        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col w-full h-full"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("book", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("المواد الدراسية — Courses").classes("text-xl font-bold app-text-primary")
                            ui.label("إدارة المواد الدراسية الخاصة بالأقسام والمراحل").classes("text-xs app-text-muted")

                    UI.success_button(
                        "+ إضافة مادة / Add Course",
                        icon="add",
                        on_click=lambda: self.show_edit_view(mode="add")
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap shrink-0"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-[300px]"):
                        def on_dept_change(e):
                            val = extract_event_value(e, default=0)
                            try:
                                self.filter_dept = int(val or 0)
                            except Exception:
                                self.filter_dept = 0
                            self.current_offset = 0
                            self._render_content()

                        UI.select(
                            label="",
                            options=filter_dept_opts,
                            value=self.filter_dept,
                            on_change=on_dept_change
                        ).classes("w-64 text-sm")

                        def on_search_change(e):
                            val = extract_event_value(e, default="")
                            self.search_term = str(val or "").strip().lower()
                            self.current_offset = 0
                            self._render_content()

                        UI.text_input(
                            label="",
                            placeholder="بحث باسم المادة... / Search course name...",
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
                def content_view():
                    self._build_table()

                content_view()
                self._refresh_content = content_view

    def _render_content(self):
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def _get_filtered_data(self) -> list[dict]:
        try:
            # CourseRepository.get_all() takes no arguments
            rows = self.repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch courses: {err}")
            rows = []

        if self.filter_dept > 0:
            target_dept = self.depts_map.get(self.filter_dept, {})
            target_name_ar = (target_dept.get("name_ar") or "").strip().lower()
            
            filtered_by_dept = []
            for r in rows:
                dept_id = r.get("department_id")
                dept_name_ar = str(r.get("dept_name_ar") or "").lower()
                
                # Match single department ID or shared department name string
                if dept_id == self.filter_dept:
                    filtered_by_dept.append(r)
                elif target_name_ar and target_name_ar in dept_name_ar:
                    filtered_by_dept.append(r)
            rows = filtered_by_dept

        if self.search_term:
            t = self.search_term
            rows = [
                r for r in rows
                if t in str(r.get("name_ar") or "").lower()
                or t in str(r.get("name_en") or "").lower()
            ]
        return rows

    def _build_table(self):
        all_rows = self._get_filtered_data()
        total_count = len(all_rows)
        
        start_idx = self.current_offset
        end_idx = start_idx + self.current_limit
        page_rows = all_rows[start_idx:end_idx]

        with ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[300px]"):
            if not page_rows:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("menu_book", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد مواد دراسية مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching courses found.").classes("text-xs app-text-muted")
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
        dept = row.get("dept_name_ar") or "—"
        if row.get("is_shared"):
            dept = f"مشتركة ({dept})" if dept and dept != "—" else "مشتركة / Shared"
            
        stage = str(row.get("stage_number", "—"))
        credits = str(row.get("credit_hours", "—"))

        with ui.row().classes("w-full items-center justify-between p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("book", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(row.get("name_ar") or "—").classes("font-bold text-base app-text-primary truncate")
                    ui.label(row.get("name_en") or "—").classes("text-xs text-slate-400 font-mono truncate")

            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("القسم / Department").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(dept).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary truncate max-w-[200px]")

                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("المرحلة / Stage").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(stage).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary")

                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("الوحدات / Credits").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(credits).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent")

            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                UI.primary_button(
                    "تعديل / Edit",
                    icon="edit",
                    on_click=lambda r=row: self.show_edit_view(row=r, mode="edit")
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

    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        self.container.clear()
        existing_data = row or {}
        cid = existing_data.get("id")

        try:
            depts = self.dept_repo.get_all() or []
        except Exception:
            depts = []
            
        dept_opts = {d["id"]: f"{d.get('name_ar', '')} / {d.get('name_en', '')}" for d in depts}

        # Track selected departments for shared courses
        shared_state = {"is_shared": bool(existing_data.get("is_shared", False))}
        selected_depts = []
        if shared_state["is_shared"] and cid:
            try:
                selected_depts = self.repo.get_shared_dept_ids(cid) or []
            except Exception as err:
                log.warning(f"Failed to fetch shared department IDs for course {cid}: {err}")
                selected_depts = []

        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col max-w-4xl mx-auto w-full"):
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.button(icon="arrow_back", on_click=self.show_list_view).props("flat round dense").classes("app-text-primary")
                        title_text = "إضافة مادة جديدة — Add Course" if mode == "add" else f"تعديل المادة — Edit {existing_data.get('name_en', '')}"
                        ui.label(title_text).classes("text-xl font-bold app-text-primary")

                with ui.column().classes("w-full gap-6 overflow-y-auto pr-1"):
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("معلومات المادة — Course Info").classes("text-base font-bold app-text-accent")

                        with ui.row().classes("w-full gap-4"):
                            name_ar_inp = UI.text_input(
                                "اسم المادة بالعربية / Arabic Name",
                                value=existing_data.get("name_ar", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                            name_en_inp = UI.text_input(
                                "اسم المادة بالإنكليزية / English Name",
                                value=existing_data.get("name_en", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            credits_inp = UI.select(
                                "الوحدات الدراسية / Credit Hours",
                                options={i: str(i) for i in range(1, 7)},
                                value=int(existing_data.get("credit_hours", 3)) if existing_data else 3
                            ).classes("flex-1 text-sm")

                            stage_inp = UI.select(
                                "المرحلة / Stage",
                                options={i: str(i) for i in range(1, 9)},
                                value=int(existing_data.get("stage_number", 1)) if existing_data else 1
                            ).classes("flex-1 text-sm")

                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("نطاق المادة — Course Scope").classes("text-base font-bold app-text-accent")

                        is_shared_chk = ui.checkbox("مادة مشتركة بين أقسام / Shared across departments", value=shared_state["is_shared"])

                        @ui.refreshable
                        def dept_selector():
                            if is_shared_chk.value:
                                ui.label("الأقسام المشتركة / Shared Departments").classes("text-sm font-bold app-text-primary mt-2")
                                with ui.row().classes("gap-4 flex-wrap w-full p-4 rounded-xl bg-[var(--bg-main)] border border-[var(--border-default)]"):
                                    for did, dname in dept_opts.items():
                                        def toggle_dept(e, d_id=did):
                                            if e.value:
                                                if d_id not in selected_depts:
                                                    selected_depts.append(d_id)
                                            else:
                                                if d_id in selected_depts:
                                                    selected_depts.remove(d_id)

                                        ui.checkbox(dname, value=(did in selected_depts)).on('update:model-value', toggle_dept)
                            else:
                                default_dept_val = existing_data.get("department_id") if existing_data and existing_data.get("department_id") else (list(dept_opts.keys())[0] if dept_opts else None)
                                dept_sel = UI.select(
                                    "القسم / Department",
                                    options=dept_opts,
                                    value=default_dept_val
                                ).classes("w-1/2 text-sm")
                                self.single_dept_sel = dept_sel

                        dept_selector()
                        is_shared_chk.on('update:model-value', dept_selector.refresh)

                    with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] shrink-0"):
                        def save_action():
                            if not depts:
                                ui.notify("يجب إضافة قسم أولاً / Please add a department first", type="warning")
                                return

                            n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                            n_en = name_en_inp.value.strip() if name_en_inp.value else ""

                            if not n_ar:
                                ui.notify("اسم المادة بالعربية مطلوب / Arabic course name is required", type="warning")
                                return
                            if not n_en:
                                ui.notify("اسم المادة بالإنكليزية مطلوب / English course name is required", type="warning")
                                return

                            is_shared = is_shared_chk.value
                            payload = {
                                "name_ar": n_ar,
                                "name_en": n_en,
                                "credit_hours": credits_inp.value,
                                "stage_number": stage_inp.value,
                            }

                            if is_shared:
                                if not selected_depts:
                                    ui.notify("اختر قسماً واحداً على الأقل / Select at least one department", type="warning")
                                    return
                                payload["department_id"] = None
                                payload["shared_dept_ids"] = list(set(selected_depts))
                            else:
                                payload["department_id"] = self.single_dept_sel.value if hasattr(self, 'single_dept_sel') and self.single_dept_sel else list(dept_opts.keys())[0]
                                payload["shared_dept_ids"] = []

                            try:
                                if mode == "add":
                                    self.repo.insert(data=payload)
                                    ui.notify("تمت إضافة المادة بنجاح / Course added", type="positive")
                                else:
                                    if cid is not None:
                                        self.repo.update(course_id=int(cid), data=payload)
                                    ui.notify("تم تعديل المادة بنجاح / Course updated", type="positive")
                                self.show_list_view()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                log.error(f"Error saving course: {err}")
                                ui.notify(f"Error: {err}", type="negative")

                        UI.secondary_button("إلغاء / Cancel", on_click=self.show_list_view).classes("text-sm px-5 py-2")
                        UI.success_button("حفظ / Save", icon="save", on_click=save_action).classes("text-sm px-5 py-2")

    def confirm_delete(self, row: dict):
        cid = row["id"]
        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد الحذف — Confirm Delete").classes("text-lg font-bold app-text-primary")
            ui.label(
                f"هل أنت متأكد من رغبتك في حذف المادة: ({row.get('name_ar', '')})؟\n"
                f"لا يمكن حذف المادة إذا كان هناك طلاب مسجلون فيها."
            ).classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_delete():
                    try:
                        self.repo.delete(cid)
                        ui.notify("تم حذف المادة / Course deleted", type="positive")
                        dialog.close()
                        self.show_list_view()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"لا يمكن الحذف (مرتبط بطلاب). / Cannot delete: {err}", type="negative")

                UI.danger_button("حذف / Delete", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()
