import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

from data.repositories import (
    GraduationOrderRepository,
    DepartmentRepository,
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


class GraduationOrdersScreen:
    """
    Graduation Orders Management Screen (NiceGUI version).
    Includes full pagination, live search, student link inspection dialog, and add/edit/delete modals.
    """
    def __init__(self, on_view_students=None):
        self.repo = GraduationOrderRepository()
        self.dept_repo = DepartmentRepository()
        self.on_view_students = on_view_students

        self.current_limit = 25
        self.current_offset = 0
        self.all_orders = []
        self.filtered_orders = []
        self.search_term = ""

        # Main viewport
        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self._build_ui()

    def _build_ui(self):
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
                        on_click=self.open_add_dialog
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row (Search Box & Limit Picker)
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-[300px]"):
                        search_inp = UI.text_input(
                            label="",
                            placeholder="بحث برقم الأمر، القسم، أو سنة التخرج... / Search by order #, dept, or year..."
                        ).classes("flex-1 text-sm")

                        def on_search_change(e):
                            self.search_term = (e.value or "").strip().lower()
                            self._apply_filter()

                        search_inp.on("update:model-value", on_search_change)

                    with ui.row().classes("items-center gap-2 shrink-0"):
                        ui.label("عرض / Show:").classes("text-xs font-bold app-text-muted")
                        limit_select = UI.select(
                            label="",
                            options={25: "25", 50: "50", 75: "75", 100: "100"},
                            value=self.current_limit
                        ).classes("w-24 text-sm")

                        def on_limit_change(e):
                            self.current_limit = int(e.value or 25)
                            self.current_offset = 0
                            self.refresh_data()

                        limit_select.on("update:model-value", on_limit_change)

                # Orders List View Area
                self.list_container = ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[300px]")

                # Pagination Footer Bar
                with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
                    self.prev_btn = UI.secondary_button(
                        "◄ السابق / Previous",
                        on_click=self.go_prev
                    ).classes("text-xs px-4 py-2")
                    
                    self.page_info_label = ui.label("—").classes("text-sm font-bold app-text-primary")

                    self.next_btn = UI.secondary_button(
                        "التالي / Next ►",
                        on_click=self.go_next
                    ).classes("text-xs px-4 py-2")

        self.refresh_data()

    def refresh_data(self):
        """Fetch orders page data from repository."""
        try:
            self.all_orders = self.repo.get_all(limit=self.current_limit, offset=self.current_offset) or []
        except Exception as err:
            log.warning(f"Failed to fetch graduation orders: {err}")
            self.all_orders = []

        self._apply_filter()

    def _apply_filter(self):
        """Filter local rows based on search input and update list UI."""
        if not self.search_term:
            self.filtered_orders = self.all_orders
        else:
            t = self.search_term
            self.filtered_orders = [
                r for r in self.all_orders
                if t in str(r.get("order_number") or "").lower()
                or t in str(r.get("dept_name_ar") or "").lower()
                or t in str(r.get("dept_name_en") or "").lower()
                or t in str(r.get("graduation_year") or "").lower()
            ]

        # Update Pagination Footer Labels & Controls
        start_idx = self.current_offset + 1 if self.filtered_orders else 0
        end_idx = self.current_offset + len(self.filtered_orders)
        self.page_info_label.text = f"السجلات {start_idx} - {end_idx}  |  Records {start_idx} - {end_idx}"

        if self.current_offset == 0:
            self.prev_btn.disable()
        else:
            self.prev_btn.enable()

        if len(self.all_orders) < self.current_limit:
            self.next_btn.disable()
        else:
            self.next_btn.enable()

        self._render_orders_list()

    def _render_orders_list(self):
        self.list_container.clear()
        with self.list_container:
            if not self.filtered_orders:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("school", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أوامر تخرج مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching graduation orders found.").classes("text-xs app-text-muted")
                return

            for row in self.filtered_orders:
                self._render_order_card(row)

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

            # Right Action Buttons: View Students, Edit, Delete
            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                UI.secondary_button(
                    "👁 الطلاب",
                    on_click=lambda r=row: self.open_view_students_dialog(r)
                ).classes("text-xs px-3 py-1.5")

                UI.primary_button(
                    "Edit / تعديل",
                    icon="edit",
                    on_click=lambda r=row: self.open_edit_dialog(r)
                ).classes("text-xs px-3 py-1.5")

                UI.danger_button(
                    "Delete / حذف",
                    icon="delete",
                    on_click=lambda r=row: self.confirm_delete(r)
                ).classes("text-xs px-3 py-1.5")

    def go_prev(self):
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self.refresh_data()

    def go_next(self):
        self.current_offset += self.current_limit
        self.refresh_data()

    # ── Dialogs: Add / Edit Order ─────────────────────────────────────────────
    def open_add_dialog(self):
        self._build_order_dialog(mode="add")

    def open_edit_dialog(self, row: dict):
        self._build_order_dialog(mode="edit", existing_data=row)

    def _build_order_dialog(self, mode: str = "add", existing_data: dict | None = None):
        # Fetch active departments list
        try:
            depts = self.dept_repo.get_all() or []
            dept_opts = {d["id"]: f"{d.get('name_ar', '')} / {d.get('name_en', '')}" for d in depts} if depts else {1: "قسم علوم الحاسوب"}
        except Exception:
            dept_opts = {1: "قسم علوم الحاسوب"}

        dialog = ui.dialog().classes("w-full max-w-2xl")
        with dialog, UI.card().classes("p-6 gap-6 w-full bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)]"):
                title = "إضافة أمر تخرج جديد — Add Graduation Order" if mode == "add" else "تعديل أمر التخرج — Edit Graduation Order"
                ui.label(title).classes("text-lg font-bold app-text-primary")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes("app-text-muted")

            with ui.column().classes("w-full gap-4"):
                # Row 1: Order Number & Date
                ui.label("بيانات الأمر الأساسية — Order Details").classes("text-sm font-bold app-text-accent")
                with ui.row().classes("w-full gap-4"):
                    order_num_inp = UI.text_input(
                        "رقم الأمر / Order Number",
                        value=existing_data.get("order_number", "") if existing_data else "",
                        placeholder="مثال: 18515/13/2"
                    ).classes("flex-1 text-sm")

                    order_date_inp = UI.text_input(
                        "تاريخ الأمر / Order Date (YYYY-MM-DD)",
                        value=existing_data.get("order_date", "") if existing_data else "",
                        placeholder="2024-06-15"
                    ).classes("flex-1 text-sm")

                # Row 2: Academic Details (Dept, Study Type, Year, Semester)
                ui.label("البيانات الأكاديمية والدراسة — Academic Details").classes("text-sm font-bold app-text-accent mt-2")
                with ui.row().classes("w-full gap-4"):
                    def_dept = existing_data.get("department_id") if existing_data else (list(dept_opts.keys())[0] if dept_opts else 1)
                    dept_sel = UI.select("القسم / Department", dept_opts, value=def_dept).classes("flex-1 text-sm")

                    def_st = existing_data.get("study_type", "morning") if existing_data else "morning"
                    st_sel = UI.select("نوع الدراسة / Study Type", STUDY_TYPE_OPTIONS, value=def_st).classes("flex-1 text-sm")

                with ui.row().classes("w-full gap-4"):
                    grad_yr_inp = UI.text_input(
                        "سنة التخرج (الدفعة) / Graduation Year",
                        value=str(existing_data.get("graduation_year", "")) if existing_data and existing_data.get("graduation_year") else "",
                        placeholder="مثال: 2024"
                    ).classes("flex-1 text-sm")

                    def_sem = existing_data.get("graduation_semester", "first") if existing_data else "first"
                    sem_sel = UI.select("فصل التخرج / Graduation Semester", SEMESTER_OPTIONS, value=def_sem).classes("flex-1 text-sm")

                # Row 3: Additional Info (Num Students, Notes)
                ui.label("معلومات إضافية — Additional Information").classes("text-sm font-bold app-text-accent mt-2")
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

            # Form Action Buttons
            with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] mt-2"):
                def save_order():
                    onum = order_num_inp.value.strip() if order_num_inp.value else ""
                    if not onum:
                        ui.notify("رقم الأمر مطلوب / Order number is required", type="warning")
                        return

                    odate = order_date_inp.value.strip() if order_date_inp.value else ""
                    if not odate or len(odate) < 8:
                        ui.notify("يرجى إدخال تاريخ أمر صالح (YYYY-MM-DD)", type="warning")
                        return

                    gyr_str = grad_yr_inp.value.strip() if grad_yr_inp.value else ""
                    if not gyr_str or not gyr_str.isdigit():
                        ui.notify("سنة التخرج مطلوبة بصيغة رقمية (مثال: 2024)", type="warning")
                        return

                    num_st_val = int(num_st_inp.value.strip()) if num_st_inp.value and num_st_inp.value.strip().isdigit() else None

                    payload = {
                        "order_number": onum,
                        "order_date": odate,
                        "department_id": dept_sel.value if isinstance(dept_sel.value, int) else 1,
                        "study_type": str(st_sel.value or "morning"),
                        "graduation_year": int(gyr_str),
                        "graduation_semester": str(sem_sel.value or "first"),
                        "num_students": num_st_val,
                        "notes": notes_inp.value.strip() if notes_inp.value else None,
                    }

                    try:
                        if mode == "add":
                            self.repo.insert(payload)
                            ui.notify("تم إضافة أمر التخرج بنجاح / Order added successfully", type="positive")
                        else:
                            self.repo.update(existing_data["id"], payload)
                            ui.notify("تم تعديل أمر التخرج بنجاح / Order updated successfully", type="positive")

                        dialog.close()
                        self.refresh_data()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"Error saving order: {err}", type="negative")

                UI.success_button("Save / حفظ", icon="save", on_click=save_order).classes("text-sm px-5 py-2")
                UI.secondary_button("Cancel / إلغاء", on_click=dialog.close).classes("text-sm px-4 py-2")

        dialog.open()

    # ── Dialog: View Linked Students ──────────────────────────────────────────
    def open_view_students_dialog(self, row: dict):
        oid = row["id"]
        order_num = row.get("order_number") or "—"

        try:
            linked_students = self.repo.get_students_for_order(oid) or []
        except Exception as err:
            log.warning(f"Error fetching linked students for order {oid}: {err}")
            linked_students = []

        dialog = ui.dialog().classes("w-full max-w-4xl")
        with dialog, UI.card().classes("p-6 gap-6 w-full bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("groups", size="md").classes("app-text-accent")
                    ui.label(f"الطلاب المرتبطون بالأمر رقم: {order_num}").classes("text-lg font-bold app-text-primary")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes("app-text-muted")

            if not linked_students:
                with ui.column().classes("w-full items-center py-10 text-center"):
                    ui.icon("group_off", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا يوجد طلاب مرتبطون بهذا الأمر حتى الآن").classes("text-base font-bold app-text-muted")
                    ui.label("No students linked to this graduation order yet.").classes("text-xs app-text-muted")
            else:
                with ui.column().classes("w-full gap-3 max-h-[450px] overflow-y-auto"):
                    for st in linked_students:
                        st_ar = st.get("full_name_ar") or st.get("name_ar") or "طالب"
                        st_en = st.get("full_name_en") or st.get("name_en") or ""
                        st_dept = st.get("dept_name_ar") or "القسم"
                        st_avg = st.get("average")
                        disp_avg = f"{float(st_avg):.2f}" if st_avg is not None else "—"

                        with ui.row().classes("w-full items-center justify-between p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-3"):
                            with ui.column().classes("flex-1 min-w-0 gap-0 text-right"):
                                ui.label(st_ar).classes("font-bold text-base app-text-primary truncate")
                                if st_en:
                                    ui.label(st_en).classes("text-xs text-slate-400 font-mono truncate")

                            with ui.row().classes("items-center gap-4 shrink-0"):
                                ui.label(st_dept).classes("text-xs font-semibold app-text-muted")
                                ui.label(f"المعدل: {disp_avg}").classes("text-sm font-bold app-text-accent")

            with ui.row().classes("w-full justify-end pt-3 border-t border-[var(--border-default)]"):
                UI.secondary_button("Close / إغلاق", on_click=dialog.close).classes("text-sm px-4 py-2")

        dialog.open()

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
                        self.refresh_data()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"Error deleting order: {err}", type="negative")

                UI.danger_button("Delete / حذف", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("Cancel / إلغاء", on_click=dialog.close).classes("text-sm px-4 py-2")

        dialog.open()
