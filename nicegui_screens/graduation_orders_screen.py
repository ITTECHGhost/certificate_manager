import logging
from datetime import datetime
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

from data.repositories import (
    GraduationOrderRepository,
    DepartmentRepository,
    StudentRepository,
    OfflineModeError,
)

log = logging.getLogger(__name__)

STUDY_TYPE_OPTIONS = {
    "morning": "صباحي / Morning",
    "evening": "مسائي / Evening",
}

SEMESTER_OPTIONS = {
    "first": "الفصل الأول / Term 1",
    "second": "الفصل الثاني / Term 2",
    "summer": "الفصل الصيفي / Summer",
}


def extract_event_value(e, default=None):
    """Safely extract primitive value from NiceGUI event object without throwing Attribute/Type Errors."""
    if isinstance(e, (int, float, str, bool)):
        return e
    if hasattr(e, "value") and not isinstance(e.value, property):
        try:
            return e.value
        except Exception:
            pass
    if hasattr(e, "args") and e.args is not None:
        try:
            args = e.args
            if isinstance(args, (list, tuple)) and len(args) > 0:
                return args[0]
            return args
        except Exception:
            pass
    return default if default is not None else (str(e) if e is not None else "")


def validate_and_format_date(date_str: str | None, label_ar: str = "التاريخ") -> tuple[bool, str | None]:
    """Validate date string YYYY-MM-DD, normalizing dots or slashes."""
    if not date_str:
        return True, None
    clean = str(date_str).strip()
    if not clean:
        return True, None

    normalized = clean.replace("/", "-").replace(".", "-")
    parts = normalized.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        try:
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            return True, dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    ui.notify(f"تاريخ غير صالح في ({label_ar}). يرجى كتابة التاريخ بصيغة YYYY-MM-DD (مثال: 2025-12-05)", type="warning")
    return False, None


class GraduationOrdersScreen:
    """
    Graduation Orders Management Screen (NiceGUI version).
    Uses FULL PAGE VIEWS (No modal dialogs) for adding, editing, and interactive student linking.
    """

    def __init__(self, on_view_students=None):
        self.repo = GraduationOrderRepository()
        self.dept_repo = DepartmentRepository()
        self.student_repo = StudentRepository()
        self.on_view_students = on_view_students

        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""

        # Main Viewport Container
        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.show_list_view()

    # ── VIEW 1: Primary Orders Table List View ──────────────────────────────
    def show_list_view(self):
        """Build main orders list table with pagination & live search."""
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("school", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إدارة أوامر التخرج — Graduation Orders").classes("text-xl font-bold app-text-primary")
                            ui.label("إدارة وحفظ الأوامر الجامعية وربطها بالدفعة والطلاب").classes("text-xs app-text-muted")

                    UI.success_button(
                        "+ إضافة أمر تخرج / Add Order",
                        icon="add",
                        on_click=lambda: self.show_edit_view(mode="add")
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row (Search Box & Limit Picker)
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-[300px]"):
                        def on_search_change(e):
                            val = extract_event_value(e, default="")
                            self.search_term = str(val or "").strip().lower()
                            self.current_offset = 0
                            self._render_content()

                        search_inp = UI.text_input(
                            label="",
                            placeholder="بحث برقم الأمر، القسم، أو سنة التخرج... / Search by order #, dept, or year...",
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

                        limit_select = UI.select(
                            label="",
                            options={25: "25", 50: "50", 75: "75", 100: "100"},
                            value=self.current_limit,
                            on_change=on_limit_change
                        ).classes("w-24 text-sm")

                # Refreshable Content Container
                @ui.refreshable
                def orders_content_view():
                    self._build_orders_table()

                orders_content_view()
                self._refresh_content = orders_content_view

    def _render_content(self):
        """Trigger view refresh."""
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def _get_filtered_orders(self) -> list[dict]:
        """Fetch and filter orders based on limit, offset, and search term."""
        try:
            fetch_limit = 500 if self.search_term else self.current_limit
            fetch_offset = 0 if self.search_term else self.current_offset

            orders = self.repo.get_all(limit=fetch_limit, offset=fetch_offset) or []
        except Exception as err:
            log.warning(f"Failed to fetch graduation orders: {err}")
            orders = []

        if not self.search_term:
            return orders

        t = self.search_term
        filtered = [
            r for r in orders
            if t in str(r.get("order_number") or "").lower()
            or t in str(r.get("dept_name_ar") or "").lower()
            or t in str(r.get("dept_name_en") or "").lower()
            or t in str(r.get("graduation_year") or "").lower()
            or t in str(r.get("order_date") or "").lower()
        ]
        return filtered

    def _build_orders_table(self):
        orders = self._get_filtered_orders()

        # Orders List Scroll Container
        with ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[340px]"):
            if not orders:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("school", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أوامر تخرج مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching graduation orders found.").classes("text-xs app-text-muted")
            else:
                for row in orders:
                    self._render_order_card(row)

        # Pagination Footer Bar
        start_idx = self.current_offset + 1 if orders else 0
        end_idx = self.current_offset + len(orders)

        with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
            prev_btn = UI.secondary_button("◄ السابق / Previous", on_click=self.go_prev).classes("text-xs px-4 py-2")
            if self.current_offset == 0 or self.search_term:
                prev_btn.disable()

            ui.label(f"السجلات {start_idx} - {end_idx}  |  Records {start_idx} - {end_idx}").classes("text-sm font-bold app-text-primary")

            next_btn = UI.secondary_button("التالي / Next ►", on_click=self.go_next).classes("text-xs px-4 py-2")
            if len(orders) < self.current_limit or self.search_term:
                next_btn.disable()

    def _render_order_card(self, row: dict):
        oid = row["id"]
        order_num = row.get("order_number") or "—"
        order_date = row.get("order_date") or "—"
        dept_name = row.get("dept_name_ar") or row.get("dept_name_en") or "جميع الأقسام"
        grad_year = row.get("graduation_year") or "—"

        st_type_raw = str(row.get("study_type") or "").lower()
        st_type_disp = STUDY_TYPE_OPTIONS.get(st_type_raw, st_type_raw or "—")

        sem_raw = str(row.get("graduation_semester") or "").lower()
        sem_disp = SEMESTER_OPTIONS.get(sem_raw, sem_raw or "—")

        linked_cnt = row.get("linked_count", 0)

        with ui.row().classes("w-full items-center justify-between p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            # Left Info Column: Order Number & Date
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("description", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(f"أمر تخرج رقم: {order_num}").classes("font-bold text-base app-text-primary truncate")
                    ui.label(f"تاريخ الأمر: {order_date}  •  القسم: {dept_name}").classes("text-xs text-slate-400 font-mono truncate")

            # Center Info Badges: Year, Study Type, Semester, Linked Students
            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("الدفعة").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(str(grad_year)).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent")

                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("الدراسة").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(st_type_disp).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary")

                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("الفصل").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(sem_disp).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary")

                with ui.column().classes("items-center gap-0 shrink-0"):
                    ui.label("الطلاب المرتبطون").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(f"👥 {linked_cnt} طالب").classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400")

            # Right Action Buttons: Combined Edit & Link Students, Delete
            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                UI.primary_button(
                    "تعديل وربط الطلاب / Edit & Link Students",
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

    # ── VIEW 2: Combined Full Page View (Edit Order + Link/Unlink Students) ─────
    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        """
        Full Page View for Editing/Adding an Order AND Managing Linked Students in one single view.
        No pop-up dialogs!
        """
        self.container.clear()

        existing_data = row or {}
        oid = existing_data.get("id")

        try:
            depts = self.dept_repo.get_all() or []
            dept_opts = {d["id"]: f"{d.get('name_ar', '')} / {d.get('name_en', '')}" for d in depts} if depts else {1: "قسم علوم الحاسوب"}
        except Exception:
            dept_opts = {1: "قسم علوم الحاسوب"}

        # State for right search panel in student linking section
        search_state = {
            "name": "",
            "dept_id": None,
            "year": None
        }

        # Department options for student linking panel search
        try:
            filter_dept_opts = {0: "كل الأقسام / All Depts"}
            filter_dept_opts.update({d["id"]: d.get("name_ar", "") for d in depts})
        except Exception:
            filter_dept_opts = {0: "كل الأقسام / All Depts"}

        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col"):
                
                # ── Top Header Navigation Bar ────────────────────────────────
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.button(icon="arrow_back", on_click=self.show_list_view).props("flat round dense").classes("app-text-primary")
                        title_text = "إضافة أمر تخرج جديد — Add Graduation Order" if mode == "add" else f"تعديل أمر التخرج ورابط الطلاب — Order #{existing_data.get('order_number', '')}"
                        ui.label(title_text).classes("text-xl font-bold app-text-primary")

                    UI.secondary_button("◄ العودة للأوامر / Back to Orders", on_click=self.show_list_view).classes("text-xs px-4 py-2")

                # Scrollable Content Area containing Order Details Form + Student Linker
                with ui.column().classes("w-full flex-1 gap-6 overflow-y-auto pr-1"):
                    
                    # ── SECTION 1: Order Details Form ─────────────────────────
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("بيانات أمر التخرج — Order Details").classes("text-base font-bold app-text-accent")

                        # Row 1: Order Number & Date
                        with ui.row().classes("w-full gap-4"):
                            order_num_inp = UI.text_input(
                                "رقم الأمر / Order Number",
                                value=existing_data.get("order_number", "") if existing_data else "",
                                placeholder="مثال: 18515/13/2"
                            ).classes("flex-1 text-sm")

                            order_date_inp = UI.text_input(
                                "تاريخ الأمر / Order Date (YYYY-MM-DD)",
                                value=existing_data.get("order_date", "") if existing_data else "",
                                placeholder="2025-12-05"
                            ).classes("flex-1 text-sm")

                        # Row 2: Academic Details (Dept, Study Type, Year, Semester)
                        with ui.row().classes("w-full gap-4"):
                            def_dept = existing_data.get("department_id") if existing_data else (list(dept_opts.keys())[0] if dept_opts else 1)
                            dept_sel = UI.select("القسم / Department", dept_opts, value=def_dept).classes("flex-1 text-sm")

                            def_st = existing_data.get("study_type", "morning") if existing_data else "morning"
                            st_sel = UI.select("نوع الدراسة / Study Type", STUDY_TYPE_OPTIONS, value=def_st).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            grad_yr_inp = UI.text_input(
                                "سنة التخرج (الدفعة) / Graduation Year",
                                value=str(existing_data.get("graduation_year", "")) if existing_data and existing_data.get("graduation_year") else "",
                                placeholder="مثال: 2025"
                            ).classes("flex-1 text-sm")

                            def_sem = existing_data.get("graduation_semester", "first") if existing_data else "first"
                            sem_sel = UI.select("فصل التخرج / Graduation Semester", SEMESTER_OPTIONS, value=def_sem).classes("flex-1 text-sm")

                        # Row 3: Student Count & Notes
                        with ui.row().classes("w-full gap-4"):
                            num_st_inp = UI.text_input(
                                "عدد الطلاب (حسب الوثيقة) / Student Count",
                                value=str(existing_data.get("num_students", "")) if existing_data and existing_data.get("num_students") else "",
                                placeholder="اختياري / Optional"
                            ).classes("flex-1 text-sm")

                            notes_inp = UI.text_input(
                                "ملاحظات / Notes",
                                value=existing_data.get("notes", "") if existing_data else "",
                                placeholder="اختياري / Optional"
                            ).classes("flex-1 text-sm")

                        # Save Order Details Button
                        with ui.row().classes("w-full justify-end gap-3 pt-2 border-t border-[var(--border-default)]"):
                            def save_order_action():
                                onum = order_num_inp.value.strip() if order_num_inp.value else ""
                                if not onum:
                                    ui.notify("رقم الأمر مطلوب / Order number is required", type="warning")
                                    return

                                odate_raw = order_date_inp.value.strip() if order_date_inp.value else ""
                                ok, formatted_date = validate_and_format_date(odate_raw, "تاريخ الأمر")
                                if not ok:
                                    return

                                gyr_str = grad_yr_inp.value.strip() if grad_yr_inp.value else ""
                                if not gyr_str or not gyr_str.isdigit():
                                    ui.notify("سنة التخرج مطلوبة بصيغة رقمية (مثال: 2025)", type="warning")
                                    return

                                num_st_val = int(num_st_inp.value.strip()) if num_st_inp.value and num_st_inp.value.strip().isdigit() else None

                                payload = {
                                    "order_number": onum,
                                    "order_date": formatted_date or odate_raw,
                                    "department_id": dept_sel.value if isinstance(dept_sel.value, int) else 1,
                                    "study_type": str(st_sel.value or "morning"),
                                    "graduation_year": int(gyr_str),
                                    "graduation_semester": str(sem_sel.value or "first"),
                                    "num_students": num_st_val,
                                    "notes": notes_inp.value.strip() if notes_inp.value else None,
                                }

                                try:
                                    if mode == "add":
                                        new_id = self.repo.insert(payload)
                                        ui.notify("تم إضافة أمر التخرج بنجاح / Order added successfully", type="positive")
                                        # Switch to edit mode for newly created order so user can link students immediately
                                        payload["id"] = new_id
                                        self.show_edit_view(row=payload, mode="edit")
                                    else:
                                        self.repo.update(oid, payload)
                                        ui.notify("تم تعديل أمر التخرج بنجاح / Order updated successfully", type="positive")
                                except OfflineModeError as err:
                                    ui.notify(str(err), type="warning")
                                except Exception as err:
                                    log.error(f"Error saving order: {err}")
                                    ui.notify(f"Error saving order: {err}", type="negative")

                            UI.success_button("💾 Save Order Details / حفظ بيانات الأمر", icon="save", on_click=save_order_action).classes("text-sm px-5 py-2")

                    # ── SECTION 2: Integrated Student Linking Panel (For Edit Mode) ──
                    if mode == "edit" and oid:
                        with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("groups", size="sm").classes("app-text-accent")
                                    ui.label("ربط وإلغاء ربط الطلاب بهذا الأمر — Link & Unlink Students").classes("text-base font-bold app-text-primary")

                                def auto_link_action():
                                    try:
                                        count = self.student_repo.auto_link_matching(oid, existing_data)
                                        ui.notify(f"تم ربط {count} طالب تلقائياً بهذا الأمر / Auto-linked {count} students", type="positive")
                                        refresh_both_student_panels()
                                    except Exception as err:
                                        ui.notify(f"Error auto-linking: {err}", type="negative")

                                UI.primary_button("🔗 ربط تلقائي المطابقين / Auto-Link Matching", on_click=auto_link_action).classes("text-xs px-4 py-2")

                            # 2-Column Panel Layout
                            with ui.row().classes("w-full gap-6 min-h-[380px] items-start"):
                                
                                # Left Column: Currently Linked Students Panel (50%)
                                with ui.column().classes("flex-1 min-h-[360px] gap-3 p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)]"):
                                    @ui.refreshable
                                    def linked_panel():
                                        try:
                                            linked_st = self.student_repo.get_by_order(oid) or []
                                        except Exception as err:
                                            log.warning(f"Error getting linked students: {err}")
                                            linked_st = []

                                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] shrink-0"):
                                            ui.label(f"الطلاب المرتبطون بالأمر ({len(linked_st)} طالب)").classes("text-sm font-bold app-text-accent")
                                            ui.label(f"Total Linked: {len(linked_st)}").classes("text-xs font-mono app-text-muted")

                                        with ui.column().classes("w-full flex-1 gap-2 overflow-y-auto max-h-[320px] pr-1"):
                                            if not linked_st:
                                                with ui.column().classes("w-full items-center py-10 text-center"):
                                                    ui.icon("group_off", size="md").classes("app-text-muted mb-1")
                                                    ui.label("لا يوجد طلاب مرتبطون بهذا الأمر").classes("text-xs font-bold app-text-muted")
                                            else:
                                                for st in linked_st:
                                                    sid = st["id"]
                                                    st_ar = st.get("full_name_ar") or "طالب"
                                                    st_avg = st.get("average")
                                                    disp_avg = f"{float(st_avg):.2f}" if st_avg is not None else "—"

                                                    with ui.row().classes("w-full items-center justify-between p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] gap-2 hover:border-[var(--color-accent)] transition-all"):
                                                        with ui.column().classes("flex-1 min-w-0 gap-0 text-right"):
                                                            ui.label(st_ar).classes("font-bold text-xs app-text-primary truncate")
                                                            ui.label(f"المعدل: {disp_avg}").classes("text-[10px] app-text-accent font-semibold")

                                                        def unlink_act(s_id=sid):
                                                            try:
                                                                self.student_repo.unlink_from_order(s_id)
                                                                ui.notify("تم إلغاء ربط الطالب / Student unlinked", type="positive")
                                                                refresh_both_student_panels()
                                                            except Exception as err:
                                                                ui.notify(f"Error unlinking: {err}", type="negative")

                                                        UI.danger_button("Unlink / إلغاء الربط", on_click=unlink_act).classes("text-[10px] px-2.5 py-1 shrink-0")

                                    linked_panel()

                                # Right Column: Unlinked Students Search & Link Panel (50%)
                                with ui.column().classes("flex-1 min-h-[360px] gap-3 p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)]"):
                                    ui.label("إضافة وربط الطلاب — Add & Link Students").classes("text-sm font-bold app-text-primary shrink-0")

                                    # Filters Row
                                    with ui.row().classes("w-full items-center gap-2 shrink-0 flex-wrap"):
                                        def on_dept_filter_change(e):
                                            val = extract_event_value(e, default=0)
                                            try:
                                                d_val = int(val or 0)
                                            except Exception:
                                                d_val = 0
                                            search_state["dept_id"] = d_val if d_val > 0 else None
                                            unlinked_panel.refresh()

                                        dept_filter = UI.select("", filter_dept_opts, value=0, on_change=on_dept_filter_change).classes("flex-1 text-xs")

                                        def on_name_filter_change(e):
                                            val = extract_event_value(e, default="")
                                            search_state["name"] = str(val or "").strip()
                                            unlinked_panel.refresh()

                                        name_filter = UI.text_input("", placeholder="بحث بالاسم... / Search name...", on_change=on_name_filter_change).classes("flex-1 text-xs")

                                    @ui.refreshable
                                    def unlinked_panel():
                                        try:
                                            unlinked_st = self.student_repo.search_unlinked(
                                                name_query=search_state["name"],
                                                dept_id=search_state["dept_id"],
                                                year=search_state["year"],
                                                limit=50
                                            ) or []
                                        except Exception as err:
                                            log.warning(f"Error searching unlinked students: {err}")
                                            unlinked_st = []

                                        with ui.column().classes("w-full flex-1 gap-2 overflow-y-auto max-h-[320px] pr-1"):
                                            if not unlinked_st:
                                                with ui.column().classes("w-full items-center py-10 text-center"):
                                                    ui.icon("search_off", size="md").classes("app-text-muted mb-1")
                                                    ui.label("لا توجد نتائج مطابقة للبحث").classes("text-xs font-bold app-text-muted")
                                            else:
                                                for st in unlinked_st:
                                                    sid = st["id"]
                                                    st_ar = st.get("full_name_ar") or "طالب"
                                                    st_dept = st.get("dept_name_ar") or "—"
                                                    is_already_linked = (st.get("order_id") == oid)

                                                    with ui.row().classes("w-full items-center justify-between p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] gap-2 hover:border-[var(--color-accent)] transition-all"):
                                                        with ui.column().classes("flex-1 min-w-0 gap-0 text-right"):
                                                            ui.label(st_ar).classes("font-bold text-xs app-text-primary truncate")
                                                            ui.label(st_dept).classes("text-[10px] app-text-muted font-semibold truncate")

                                                        if is_already_linked:
                                                            ui.label("مرتبط ✅").classes("text-[10px] font-bold text-emerald-400 px-2 py-1 bg-emerald-500/10 rounded-md")
                                                        else:
                                                            def link_act(s_id=sid):
                                                                try:
                                                                    self.student_repo.link_to_order(s_id, oid)
                                                                    ui.notify("تم ربط الطالب بالأمر / Student linked", type="positive")
                                                                    refresh_both_student_panels()
                                                                except Exception as err:
                                                                    ui.notify(f"Error linking: {err}", type="negative")

                                                            UI.success_button("Link / ربط ➕", on_click=link_act).classes("text-[10px] px-2.5 py-1 shrink-0")

                                    unlinked_panel()

                            def refresh_both_student_panels():
                                linked_panel.refresh()
                                unlinked_panel.refresh()

    # ── Confirm Delete ────────────────────────────────────────────────────────
    def confirm_delete(self, row: dict):
        oid = row["id"]
        order_num = row.get("order_number") or "—"
        linked_cnt = row.get("linked_count", 0)

        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد حذف أمر التخرج — Delete Graduation Order").classes("text-lg font-bold app-text-primary")
            ui.label(
                f"هل أنت تأكد من رغبتك في حذف الأمر: ({order_num})؟\n"
                f"سيتم إلغاء ربط جميع الطلاب ({linked_cnt} طالب) المرتبطين بهذا الأمر."
            ).classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_delete():
                    try:
                        self.repo.delete(oid)
                        ui.notify("تم حذف أمر التخرج بنجاح / Order deleted", type="positive")
                        dialog.close()
                        self.show_list_view()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"Error deleting order: {err}", type="negative")

                UI.danger_button("Delete / حذف", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("Cancel / إلغاء", on_click=dialog.close).classes("text-sm px-4 py-2")

        dialog.open()
