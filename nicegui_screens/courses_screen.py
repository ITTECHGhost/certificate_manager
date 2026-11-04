import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import CourseRepository, DepartmentRepository, StudyRoutineRepository, StudySystemRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value
from nicegui_screens.study_routines_screen import StudyRoutinesController

log = logging.getLogger(__name__)

class CoursesScreen:
    """
    Courses Management Screen (NiceGUI version).
    Includes Course Catalog and Predefined Study Routines management tabs.
    """

    def __init__(self):
        self.repo = CourseRepository()
        self.dept_repo = DepartmentRepository()
        self.routine_repo = StudyRoutineRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""
        self.filter_dept = 0

        self.container = ui.column().classes("w-full gap-4")
        self.show_list_view()

    def show_list_view(self):
        self.container.clear()

        try:
            depts = self.dept_repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch departments for course filter: {err}")
            depts = []

        self.depts_list = depts
        self.depts_map = {d["id"]: d for d in depts}
        filter_dept_opts = {0: "كل الأقسام"}
        for d in depts:
            filter_dept_opts[d["id"]] = d.get('name_ar', '')

        with self.container:
            with ui.tabs().classes("w-full shrink-0").props("align=left") as tabs:
                ui.tab("courses", label="دليل المواد الدراسية", icon="book")
                ui.tab("routines", label="الروتينات الدراسية الجاهزة", icon="playlist_add_check")

            with ui.tab_panels(tabs, value="courses").classes("w-full bg-transparent"):
                # Panel 1: Course Catalog
                with ui.tab_panel("courses").classes("w-full p-0 pt-4"):
                    with UI.card():
                        # Toolbar: search, department filter, then the one primary action
                        with ui.row().classes("w-full items-center gap-2"):
                            def on_search_change(e):
                                val = extract_event_value(e, default="")
                                self.search_term = str(val or "").strip().lower()
                                self.current_offset = 0
                                self._render_content()

                            UI.search_input(
                                placeholder="ابحث باسم المادة",
                                on_change=on_search_change,
                            ).classes("flex-1 min-w-[200px] max-w-sm")

                            def on_dept_change(e):
                                val = extract_event_value(e, default=0)
                                try:
                                    self.filter_dept = int(val or 0)
                                except Exception:
                                    self.filter_dept = 0
                                self.current_offset = 0
                                self._render_content()

                            UI.select(
                                label="القسم",
                                options=filter_dept_opts,
                                value=self.filter_dept,
                                on_change=on_dept_change
                            ).classes("min-w-[220px]", remove="w-full")

                            ui.space()
                            UI.primary_button("إضافة مادة", icon="add", on_click=lambda: self.show_edit_view(mode="add"))

                        @ui.refreshable
                        def content_view():
                            self._build_table()

                        content_view()
                        self._refresh_content = content_view

                # Panel 2: Predefined Study Routines (Master-Detail View), built the first time it is opened
                with ui.tab_panel("routines").classes("w-full p-0 pt-4") as routines_panel:
                    pass

            def _open_routines(e):
                if getattr(e, "value", None) == "routines" and not routines_panel.default_slot.children:
                    with routines_panel:
                        StudyRoutinesController(standalone=False).render_master_detail_view()

            tabs.on_value_change(_open_routines)

    def _render_content(self):
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def _get_filtered_data(self) -> list[dict]:
        try:
            rows = self.repo.get_all_newest_first() or []
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
        """Read-only rows; click a row to edit it in a dialog."""
        all_rows = self._get_filtered_data()
        total_count = len(all_rows)
        if not all_rows:
            if self.search_term or self.filter_dept:
                UI.empty_state("لا توجد مادة مطابقة", "غيّر البحث أو اختر «كل الأقسام».", icon="search_off")
            else:
                UI.empty_state("لا توجد مواد بعد", "أضف أول مادة دراسية.", icon="menu_book",
                               action_text="إضافة مادة", on_action=lambda: self.show_edit_view(mode="add"))
            return

        self.current_offset = min(self.current_offset, (total_count - 1) // self.current_limit * self.current_limit)
        page_rows = all_rows[self.current_offset:self.current_offset + self.current_limit]
        rows = [{
            "id": r.get("id"),
            "name_ar": r.get("name_ar") or "—",
            "name_en": r.get("name_en") or "",
            "dept": r.get("dept_name_ar") or ("مشتركة" if r.get("is_shared") else "—"),
            "stage": r.get("stage_number") or "—",
            "credits": r.get("credit_hours") or "—",
            "raw": r,
        } for r in page_rows]

        table = UI.data_table([
            {"name": "name_ar", "label": "المادة", "field": "name_ar", "align": "right"},
            {"name": "dept", "label": "القسم", "field": "dept"},
            {"name": "stage", "label": "المرحلة", "field": "stage"},
            {"name": "credits", "label": "الوحدات", "field": "credits"},
            {"name": "actions", "label": "", "field": "actions"},
        ], rows, clickable=True)
        table.add_slot("body-cell-name_ar", """
            <q-td :props="props">
                <div class="flex flex-col text-right leading-tight">
                    <span class="font-semibold app-text-primary">{{ props.row.name_ar }}</span>
                    <span class="app-caption" dir="ltr">{{ props.row.name_en }}</span>
                </div>
            </q-td>
        """)
        table.add_slot("body-cell-actions", """
            <q-td :props="props" auto-width>
                <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف المادة"
                       @click.stop="$parent.$emit('delete_course', props.row)">
                    <q-tooltip>حذف المادة</q-tooltip>
                </q-btn>
            </q-td>
        """)
        table.on("rowClick", lambda e: self.show_edit_view(row=e.args[1].get("raw"), mode="edit"))
        table.on("delete_course", lambda e: self.confirm_delete(e.args.get("raw") or e.args))

        UI.paginator(total_count, self.current_offset // self.current_limit + 1, self.current_limit, self._go_to_page)

    def _go_to_page(self, page: int):
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
        self._render_content()

    # -----------------------------------------------------------------------
    # Predefined Routines Management View
    # -----------------------------------------------------------------------
    def _build_routines_list(self):
        try:
            routines = self.routine_repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch routines: {err}")
            routines = []

        with ui.column().classes("w-full gap-4"):
            if not routines:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("playlist_add_check", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد روتينات دراسية مضافة حتى الآن").classes("text-lg font-bold app-text-muted")
                    ui.label("اضغط زر '+ إضافة روتين جديد' لتحديد حزمة مواد مرحلة وفصل دراسي.").classes("text-xs app-text-muted mt-1")
            else:
                for r in routines:
                    self._render_routine_card(r)

    def _render_routine_card(self, routine: dict):
        rid = routine["id"]
        name_ar = routine.get("name_ar") or "روتين"
        name_en = routine.get("name_en") or ""
        dept_name = routine.get("dept_name_ar") or "قسم غير مخصص"
        courses = routine.get("courses") or []

        # Group courses by Stage (1..4) for display
        courses_by_stage = {}
        for c in courses:
            stg = int(c.get("stage_number") or 1)
            if stg not in courses_by_stage:
                courses_by_stage[stg] = []
            courses_by_stage[stg].append(c)

        with UI.card().classes("w-full p-5 gap-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-3 pb-3 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("playlist_add_check", size="md").classes("app-text-accent")
                    with ui.column().classes("gap-0"):
                        ui.label(name_ar).classes("font-bold text-lg app-text-primary")
                        if name_en:
                            ui.label(name_en).classes("text-xs text-slate-400 font-mono")

                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.label(f"القسم: {dept_name}").classes("text-xs font-bold px-3 py-1.5 rounded-lg bg-[var(--bg-main)] border border-[var(--border-default)] app-text-primary")
                    ui.label("الخطة الكاملة (4 سنوات)").classes("text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400")
                    ui.label(f"إجمالي المواد: {len(courses)} مادة").classes("text-xs font-bold px-3 py-1.5 rounded-lg bg-[var(--bg-main)] border border-[var(--border-default)] app-text-accent")

                    UI.primary_button("", icon="edit", on_click=lambda rt=routine: self.show_routine_edit_dialog(rt)).props("round dense").classes("text-xs p-1.5 ml-2").tooltip("تعديل")
                    UI.danger_button("", icon="delete", on_click=lambda rt=routine: self.confirm_delete_routine(rt)).props("round dense").classes("text-xs p-1.5").tooltip("حذف")

            with ui.column().classes("w-full gap-3 pt-1"):
                if not courses:
                    ui.label("لا توجد مواد مضافة في هذا الروتين").classes("text-xs italic text-amber-500 p-2")
                else:
                    with ui.row().classes("w-full gap-4 flex-wrap grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4"):
                        stage_labels = {1: "المرحلة الأولى", 2: "المرحلة الثانية", 3: "المرحلة الثالثة", 4: "المرحلة الرابعة"}
                        for stg_num in range(1, 5):
                            stg_courses = courses_by_stage.get(stg_num, [])
                            with ui.column().classes("w-full p-3 rounded-xl bg-[var(--bg-main)] border border-[var(--border-default)] gap-2"):
                                with ui.row().classes("w-full justify-between items-center pb-1 border-b border-[var(--border-default)]"):
                                    ui.label(stage_labels[stg_num]).classes("text-xs font-bold app-text-accent")
                                    ui.label(f"{len(stg_courses)} مادة").classes("text-[10px] font-bold text-slate-400")

                                if not stg_courses:
                                    ui.label("لا توجد مواد").classes("text-[11px] italic text-slate-400")
                                else:
                                    for c in stg_courses:
                                        c_name = c.get("name_ar", "مادة")
                                        c_sem = "ف1" if int(c.get("semester_num") or 1) == 1 else "ف2"
                                        c_units = c.get("credit_hours", 1)
                                        ui.label(f"• [{c_sem}] {c_name} ({c_units}و)").classes("text-xs font-medium text-slate-700 dark:text-slate-300 truncate w-full")

    def show_routine_edit_dialog(self, routine: dict | None = None):
        existing = routine or {}
        rid = existing.get("id")
        
        try:
            depts = self.dept_repo.get_all() or []
        except Exception:
            depts = []

        dept_opts = {d["id"]: f"{d.get('name_ar', '')} / {d.get('name_en', '')}" for d in depts}
        if not dept_opts:
            ui.notify("يرجى إضافة قسم واحد على الأقل أولاً", type="warning")
            return

        try:
            all_courses = self.repo.get_all() or []
        except Exception:
            all_courses = []

        init_dept = existing.get("department_id") or list(dept_opts.keys())[0]
        init_sys = existing.get("study_system_id", 1)
        
        existing_courses = existing.get("courses") or []
        if existing_courses:
            selected_course_ids = set(c["id"] for c in existing_courses if "id" in c)
        else:
            selected_course_ids = set(existing.get("course_ids") or [])

        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-5 w-full max-w-6xl bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)] shadow-2xl overflow-hidden"):
            with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)] shrink-0"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("playlist_add_check", size="md").classes("app-text-accent")
                    with ui.column().classes("gap-0"):
                        title_txt = f"تعديل الخطة الدراسية (4 سنوات): {existing.get('name_ar')}" if rid else "إضافة خطة دراسية جديدة (4 سنوات)"
                        ui.label(title_txt).classes("text-lg font-bold app-text-primary")
                        ui.label("تحديد الخطة الكاملة للقسم وتوزيع المواد على جميع المراحل (1-4) والفصول الدراسية").classes("text-xs app-text-muted")

            with ui.column().classes("w-full gap-4 overflow-y-auto max-h-[75vh] pr-1"):
                with ui.row().classes("w-full gap-3 items-center flex-nowrap py-1"):
                    name_ar_inp = UI.text_input("اسم الروتين (عربي)", value=existing.get("name_ar", "")).classes("flex-1 min-w-0 text-sm")
                    name_en_inp = UI.text_input("اسم الروتين (إنكليزي)", value=existing.get("name_en", "")).classes("flex-1 min-w-0 text-sm")
                    dept_sel = UI.select("القسم", options=dept_opts, value=init_dept).classes("w-56 shrink-0 text-sm")
                    sys_sel = UI.select("النظام الدراسي", options={1: "سنوي", 2: "فصلي", 3: "مقررات"}, value=init_sys).classes("w-36 shrink-0 text-sm")

                @ui.refreshable
                def render_stages_view():
                    try:
                        target_dept_id = int(dept_sel.value or 0)
                    except Exception:
                        target_dept_id = 0

                    filtered_courses = []
                    for c in all_courses:
                        try:
                            c_dept_id = int(c.get("department_id") or 0)
                        except Exception:
                            c_dept_id = 0
                        is_sh = bool(c.get("is_shared"))
                        if c_dept_id == target_dept_id or is_sh or target_dept_id == 0 or c_dept_id == 0:
                            filtered_courses.append(c)

                    course_dropdown_opts = {}
                    for c in filtered_courses:
                        cid = c["id"]
                        c_ar = c.get("name_ar", "مادة")
                        c_en = c.get("name_en", "")
                        units = c.get("credit_hours", 1)
                        stg = c.get("stage_number", 1)
                        label = f"المرحلة {stg} — {c_ar}" + f" ({units} وحدة)"
                        course_dropdown_opts[cid] = label

                    with ui.tabs().classes("w-full bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)] p-1 shrink-0") as stage_tabs:
                        t1 = ui.tab("stg1", label="المرحلة 1 (السنة الأولى)", icon="looks_one")
                        t2 = ui.tab("stg2", label="المرحلة 2 (السنة الثانية)", icon="looks_two")
                        t3 = ui.tab("stg3", label="المرحلة 3 (السنة الثالثة)", icon="looks_3")
                        t4 = ui.tab("stg4", label="المرحلة 4 (السنة الرابعة)", icon="looks_4")

                    with ui.tab_panels(stage_tabs, value=t1).classes("w-full p-0 bg-transparent"):
                        for stg_num, tab_obj in [(1, t1), (2, t2), (3, t3), (4, t4)]:
                            with ui.tab_panel(tab_obj).classes("w-full p-0 pt-3 bg-transparent"):
                                stg_added = [c for c in filtered_courses if c["id"] in selected_course_ids and int(c.get("stage_number") or 1) == stg_num]
                                sem1_added = [c for c in stg_added if int(c.get("semester_num") or 1) == 1]
                                sem2_added = [c for c in stg_added if int(c.get("semester_num") or 1) == 2]

                                other_added = [c for c in stg_added if int(c.get("semester_num") or 1) not in (1, 2)]
                                if other_added:
                                    sem1_added.extend(other_added)

                                with ui.column().classes("w-full gap-4"):
                                    with ui.column().classes("w-full p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-3"):
                                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] flex-wrap gap-2"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon("looks_one", size="xs").classes("app-text-accent")
                                                ui.label("الفصل الدراسي الأول").classes("text-xs font-bold app-text-primary")
                                                ui.label(f"({len(sem1_added)} مادة مختارة)").classes("text-[10px] app-text-accent font-bold")

                                        if course_dropdown_opts:
                                            with ui.row().classes("w-full gap-2 items-center p-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-default)] flex-nowrap"):
                                                init_c1 = list(course_dropdown_opts.keys())[0]
                                                sem1_select = UI.select("إضافة مادة للفصل الأول", course_dropdown_opts, value=init_c1, with_input=True).classes("flex-1 min-w-0 text-sm")
                                                
                                                def do_add_sem1(sel_widget=sem1_select):
                                                    cid = sel_widget.value
                                                    if cid:
                                                        selected_course_ids.add(cid)
                                                        ui.notify("تم إضافة المادة إلى الروتين", type="positive")
                                                        render_stages_view.refresh()

                                                UI.success_button("+ إضافة مادة", icon="add", on_click=do_add_sem1).classes("text-xs px-4 py-2 shrink-0")

                                        with ui.row().classes("w-full gap-3 flex-wrap grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3"):
                                            if not sem1_added:
                                                ui.label("لم يتم إضافة مواد لهذا الفصل بعد. اختر مادة من القائمة أعلاه واضغط (+ إضافة مادة).").classes("text-xs italic text-slate-400 p-3 col-span-full")
                                            else:
                                                for c in sem1_added:
                                                    cid = c["id"]
                                                    c_name = c.get("name_ar") or c.get("name_en") or "مادة"
                                                    c_units = c.get("credit_hours", 1)

                                                    def make_del1(course_id=cid):
                                                        def _del():
                                                            selected_course_ids.discard(course_id)
                                                            render_stages_view.refresh()
                                                        return _del

                                                    box_cls = "items-center gap-2 p-3 rounded-xl border border-[var(--color-accent)] bg-[var(--bg-card)] shadow-sm justify-between"
                                                    with ui.row().classes(box_cls):
                                                        with ui.row().classes("items-center gap-2 flex-1 min-w-0"):
                                                            ui.icon("book", size="xs").classes("app-text-accent")
                                                            with ui.column().classes("gap-0 min-w-0"):
                                                                ui.label(c_name).classes("text-xs font-bold app-text-primary truncate w-full")
                                                                ui.label(f"{c_units} وحدات دراسية").classes("text-[10px] text-slate-400")
                                                        ui.button("حذف", icon="delete", on_click=make_del1(cid)).props("flat dense").classes("text-rose-400 text-xs shrink-0 font-bold")

                                    with ui.column().classes("w-full p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-3"):
                                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] flex-wrap gap-2"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon("looks_two", size="xs").classes("app-text-accent")
                                                ui.label("الفصل الدراسي الثاني").classes("text-xs font-bold app-text-primary")
                                                ui.label(f"({len(sem2_added)} مادة مختارة)").classes("text-[10px] app-text-accent font-bold")

                                        if course_dropdown_opts:
                                            with ui.row().classes("w-full gap-2 items-center p-2 rounded-lg bg-[var(--bg-main)] border border-[var(--border-default)] flex-nowrap"):
                                                init_c2 = list(course_dropdown_opts.keys())[0]
                                                sem2_select = UI.select("إضافة مادة للفصل الثاني", course_dropdown_opts, value=init_c2, with_input=True).classes("flex-1 min-w-0 text-sm")
                                                
                                                def do_add_sem2(sel_widget=sem2_select):
                                                    cid = sel_widget.value
                                                    if cid:
                                                        selected_course_ids.add(cid)
                                                        ui.notify("تم إضافة المادة إلى الروتين", type="positive")
                                                        render_stages_view.refresh()

                                                UI.success_button("+ إضافة مادة", icon="add", on_click=do_add_sem2).classes("text-xs px-4 py-2 shrink-0")

                                        with ui.row().classes("w-full gap-3 flex-wrap grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3"):
                                            if not sem2_added:
                                                ui.label("لم يتم إضافة مواد لهذا الفصل بعد. اختر مادة من القائمة أعلاه واضغط (+ إضافة مادة).").classes("text-xs italic text-slate-400 p-3 col-span-full")
                                            else:
                                                for c in sem2_added:
                                                    cid = c["id"]
                                                    c_name = c.get("name_ar") or c.get("name_en") or "مادة"
                                                    c_units = c.get("credit_hours", 1)

                                                    def make_del2(course_id=cid):
                                                        def _del():
                                                            selected_course_ids.discard(course_id)
                                                            render_stages_view.refresh()
                                                        return _del

                                                    box_cls = "items-center gap-2 p-3 rounded-xl border border-[var(--color-accent)] bg-[var(--bg-card)] shadow-sm justify-between"
                                                    with ui.row().classes(box_cls):
                                                        with ui.row().classes("items-center gap-2 flex-1 min-w-0"):
                                                            ui.icon("book", size="xs").classes("app-text-accent")
                                                            with ui.column().classes("gap-0 min-w-0"):
                                                                ui.label(c_name).classes("text-xs font-bold app-text-primary truncate w-full")
                                                                ui.label(f"{c_units} وحدات دراسية").classes("text-[10px] text-slate-400")
                                                        ui.button("حذف", icon="delete", on_click=make_del2(cid)).props("flat dense").classes("text-rose-400 text-xs shrink-0 font-bold")

                render_stages_view()
                dept_sel.on('update:model-value', render_stages_view.refresh)

            with ui.row().classes("w-full justify-between items-center pt-4 border-t border-[var(--border-default)] shrink-0"):
                ui.label(f"إجمالي المواد المشمولة في الروتين الكامل: {len(selected_course_ids)} مادة").classes("text-xs font-bold app-text-muted")
                
                with ui.row().classes("items-center gap-3"):
                    def save_routine_action():
                        n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                        n_en = name_en_inp.value.strip() if name_en_inp.value else ""
                        if not n_ar:
                            ui.notify("يرجى كتابة اسم الروتين بالعربية", type="warning")
                            return

                        payload = {
                            "name_ar": n_ar,
                            "name_en": n_en,
                            "department_id": int(dept_sel.value or 1),
                            "study_system_id": int(sys_sel.value or 1),
                            "stage_number": 1,
                            "semester_num": 1,
                            "course_ids": list(selected_course_ids)
                        }

                        try:
                            if rid:
                                self.routine_repo.update(rid, payload)
                                ui.notify("تم تعديل الروتين بنجاح", type="positive")
                            else:
                                self.routine_repo.insert(payload)
                                ui.notify("تم إضافة الروتين بنجاح", type="positive")
                            dialog.close()
                            if hasattr(self, "_refresh_routines") and self._refresh_routines:
                                self._refresh_routines.refresh()
                            else:
                                self.show_list_view()
                        except Exception as err:
                            log.error(f"Error saving routine: {err}")
                            ui.notify(f"تعذر حفظ الخطة الدراسية: {err}", type="negative")

                    UI.secondary_button("إلغاء", on_click=dialog.close).classes("text-sm px-5 py-2")
                    UI.success_button("حفظ الخطة الدراسية", icon="save", on_click=save_routine_action).classes("text-sm px-5 py-2")

        dialog.open()

    def confirm_delete_routine(self, routine: dict):
        rid = routine["id"]
        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد الحذف").classes("text-lg font-bold app-text-primary")
            ui.label(f"هل أنت متأكد من رغبتك في حذف الروتين: ({routine.get('name_ar')})؟\nلن يؤثر ذلك على الطلاب المسجلين سابقاً.").classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_del():
                    try:
                        self.routine_repo.delete(rid)
                        ui.notify("تم حذف الروتين", type="positive")
                        dialog.close()
                        if hasattr(self, "_refresh_routines"):
                            self._refresh_routines.refresh()
                    except Exception as err:
                        ui.notify(f"خطأ أثناء الحذف: {err}", type="negative")

                UI.danger_button("حذف", icon="delete", on_click=do_del).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()

    # -----------------------------------------------------------------------
    # Course Catalog Add/Edit View
    # -----------------------------------------------------------------------
    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        """Add or edit one course in a dialog over the list."""
        existing_data = row or {}
        cid = existing_data.get("id")

        try:
            depts = self.dept_repo.get_all() or []
        except Exception:
            depts = []
            
        dept_opts = {d["id"]: d.get('name_ar', '') for d in depts}

        shared_state = {"is_shared": bool(existing_data.get("is_shared", False))}
        selected_depts = []
        if shared_state["is_shared"] and cid:
            try:
                selected_depts = self.repo.get_shared_dept_ids(cid) or []
            except Exception as err:
                log.warning(f"Failed to fetch shared department IDs for course {cid}: {err}")
                selected_depts = []

        dialog = ui.dialog()

        def _done():
            dialog.close()
            self._render_content()

        with dialog:
            with ui.card().classes("app-dialog w-[680px] max-w-full gap-4"):
                title_text = "إضافة مادة جديدة" if mode == "add" else f"تعديل المادة: {existing_data.get('name_ar', '')}"
                ui.label(title_text).classes("app-section-title")

                with ui.column().classes("w-full gap-4"):
                    with ui.column().classes("w-full gap-4"):

                        with ui.row().classes("w-full gap-4"):
                            name_ar_inp = UI.text_input(
                                "اسم المادة بالعربية",
                                value=existing_data.get("name_ar", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                            name_en_inp = UI.text_input(
                                "اسم المادة بالإنكليزية",
                                value=existing_data.get("name_en", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            credits_inp = UI.select(
                                "الوحدات الدراسية",
                                options={i: str(i) for i in range(1, 7)},
                                value=int(existing_data.get("credit_hours", 3)) if existing_data else 3
                            ).classes("flex-1 text-sm")

                            stage_inp = UI.select(
                                "المرحلة",
                                options={i: str(i) for i in range(1, 9)},
                                value=int(existing_data.get("stage_number", 1)) if existing_data else 1
                            ).classes("flex-1 text-sm")

                    with ui.column().classes("w-full gap-2"):
                        ui.label("نطاق المادة").classes("app-section-title")

                        is_shared_chk = ui.checkbox("مادة مشتركة بين أقسام", value=shared_state["is_shared"])

                        @ui.refreshable
                        def dept_selector():
                            if is_shared_chk.value:
                                ui.label("الأقسام المشتركة").classes("text-sm font-bold app-text-primary mt-2")
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
                                    "القسم",
                                    options=dept_opts,
                                    value=default_dept_val
                                ).classes("w-1/2 text-sm")
                                self.single_dept_sel = dept_sel

                        dept_selector()
                        is_shared_chk.on('update:model-value', dept_selector.refresh)

                    with ui.row().classes("app-dialog-actions"):
                        def save_action():
                            if not depts:
                                ui.notify("يجب إضافة قسم أولاً", type="warning")
                                return

                            n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                            n_en = name_en_inp.value.strip() if name_en_inp.value else ""

                            if not n_ar:
                                ui.notify("اسم المادة بالعربية مطلوب", type="warning")
                                return
                            if not n_en:
                                ui.notify("اسم المادة بالإنكليزية مطلوب", type="warning")
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
                                    ui.notify("اختر قسماً واحداً على الأقل", type="warning")
                                    return
                                payload["department_id"] = None
                                payload["shared_dept_ids"] = list(set(selected_depts))
                            else:
                                payload["department_id"] = self.single_dept_sel.value if hasattr(self, 'single_dept_sel') and self.single_dept_sel else list(dept_opts.keys())[0]
                                payload["shared_dept_ids"] = []

                            try:
                                if mode == "add":
                                    self.repo.insert(data=payload)
                                    ui.notify("تمت إضافة المادة بنجاح", type="positive")
                                else:
                                    if cid is not None:
                                        self.repo.update(course_id=int(cid), data=payload)
                                    ui.notify("تم تعديل المادة بنجاح", type="positive")
                                _done()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                log.error(f"Error saving course: {err}")
                                ui.notify(f"تعذر الحفظ: {err}", type="negative")

                        UI.ghost_button("إلغاء", on_click=dialog.close)
                        UI.primary_button("حفظ", icon="save", on_click=save_action)
        dialog.open()

    def confirm_delete(self, row: dict):
        cid = row["id"]
        name_ar = row.get("name_ar", "")

        def do_delete():
            try:
                self.repo.delete(cid)
                UI.notify(f"تم حذف المادة ({name_ar})", type="positive")
                self._render_content()
            except OfflineModeError as err:
                UI.notify(str(err), type="warning")
            except Exception as err:
                UI.notify(f"تعذر حذف المادة: هي مرتبطة بدرجات طلاب. {err}", type="negative")

        UI.confirm_dialog(
            "حذف المادة",
            f"ستُحذف المادة ({name_ar}). لا يمكن حذفها إذا كان لطلاب درجات فيها.",
            "حذف المادة",
            do_delete,
        )
