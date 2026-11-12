import logging
from datetime import datetime
from utils.date_parsing import format_academic_year
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

from data.repositories import (
    GraduationOrderRepository,
    DepartmentRepository,
    StudentRepository,
    OfflineModeError,
)

from nicegui_screens.order_workspace import OrderWorkspaceMixin

log = logging.getLogger(__name__)

STUDY_TYPE_OPTIONS = {
    "morning": "صباحي",
    "evening": "مسائي",
}

SEMESTER_OPTIONS = {
    "first": "الفصل الأول",
    "second": "الفصل الثاني",
    "summer": "الفصل الصيفي",
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

    from utils.date_parsing import parse_date
    parsed = parse_date(clean)
    if parsed:
        return True, parsed

    ui.notify(f"تاريخ غير صالح في ({label_ar}). اكتبه مثل 2025-10-13 أو 13/10/2025", type="warning")
    return False, None


class GraduationOrdersScreen(OrderWorkspaceMixin):
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
        self.container = ui.column().classes("w-full gap-4")
        self.show_list_view()

    # ── VIEW 1: Orders list ──────────────────────────────────────────────────
    def show_list_view(self):
        """Orders list: search and add in one row, read-only rows (click to open), one paginator."""
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2"):
                    def on_search_change(e):
                        val = extract_event_value(e, default="")
                        self.search_term = str(val or "").strip().lower()
                        self.current_offset = 0
                        self._render_content()

                    UI.search_input(
                        placeholder="ابحث برقم الأمر أو القسم أو سنة التخرج",
                        on_change=on_search_change,
                    ).classes("flex-1 min-w-[220px] max-w-md")
                    ui.space()
                    UI.primary_button("إضافة أمر تخرج", icon="add", on_click=lambda: self.show_edit_view(mode="add"))

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
        """All orders (newest first, from the local copy), filtered by the search text."""
        try:
            orders = self.repo.get_all(limit=1000, offset=0) or []
        except Exception as err:
            log.warning(f"Failed to fetch graduation orders: {err}")
            orders = []

        if not self.search_term:
            return orders

        t = self.search_term
        return [
            r for r in orders
            if t in str(r.get("order_number") or "").lower()
            or t in str(r.get("dept_name_ar") or "").lower()
            or t in str(r.get("graduation_year") or "").lower()
            or t in str(r.get("order_date") or "").lower()
        ]

    def _build_orders_table(self):
        orders = self._get_filtered_orders()
        total = len(orders)
        if not orders:
            if self.search_term:
                UI.empty_state("لا يوجد أمر مطابق", "تحقق من رقم الأمر أو امسح البحث.", icon="search_off")
            else:
                UI.empty_state("لا توجد أوامر تخرج بعد", "أضف أول أمر ثم اربط به الطلاب.", icon="school",
                               action_text="إضافة أمر تخرج", on_action=lambda: self.show_edit_view(mode="add"))
            return

        self.current_offset = min(self.current_offset, (total - 1) // self.current_limit * self.current_limit)
        page_rows = orders[self.current_offset:self.current_offset + self.current_limit]
        rows = []
        for r in page_rows:
            st_raw = str(r.get("study_type") or "").lower()
            sem_raw = str(r.get("graduation_semester") or "").lower()
            rows.append({
                "id": r["id"],
                "order_number": r.get("order_number") or "—",
                "order_date": r.get("order_date") or "—",
                "dept": r.get("dept_name_ar") or "جميع الأقسام",
                "year": format_academic_year(r.get("graduation_year")) or r.get("graduation_year") or "—",
                "term": " • ".join(x for x in (STUDY_TYPE_OPTIONS.get(st_raw, ""), SEMESTER_OPTIONS.get(sem_raw, "")) if x) or "—",
                "linked": r.get("linked_count", 0) or 0,
                "raw": r,
            })

        table = UI.data_table([
            {"name": "order_number", "label": "رقم الأمر", "field": "order_number", "align": "right"},
            {"name": "order_date", "label": "تاريخ الأمر", "field": "order_date"},
            {"name": "dept", "label": "القسم", "field": "dept"},
            {"name": "year", "label": "الدفعة", "field": "year"},
            {"name": "term", "label": "الدراسة والفصل", "field": "term"},
            {"name": "linked", "label": "الطلاب المرتبطون", "field": "linked"},
            {"name": "actions", "label": "", "field": "actions"},
        ], rows, clickable=True)
        # Order number and date are what people look for: make them stand out
        table.add_slot("body-cell-order_number", """
            <q-td :props="props"><span class="font-bold app-text-primary text-base" dir="ltr">{{ props.value }}</span></q-td>
        """)
        table.add_slot("body-cell-order_date", """
            <q-td :props="props"><span class="font-semibold app-text-primary" dir="ltr">{{ props.value }}</span></q-td>
        """)
        table.add_slot("body-cell-actions", """
            <q-td :props="props" auto-width>
                <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف الأمر"
                       @click.stop="$parent.$emit('delete_order', props.row)">
                    <q-tooltip>حذف الأمر</q-tooltip>
                </q-btn>
            </q-td>
        """)
        table.on("rowClick", lambda e: self.show_edit_view(row=e.args[1].get("raw"), mode="edit"))
        table.on("delete_order", lambda e: self.confirm_delete(e.args.get("raw") or e.args))

        UI.paginator(total, self.current_offset // self.current_limit + 1, self.current_limit, self._go_to_page)

    def _go_to_page(self, page: int):
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
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
            dept_opts = {d["id"]: d.get('name_ar', '') for d in depts} if depts else {1: "قسم علوم الحاسوب"}
        except Exception:
            dept_opts = {1: "قسم علوم الحاسوب"}

        with self.container:
            with UI.card().classes("flex-1 gap-6"):

                # ── Header: back, then which order this is ──────────────────
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    UI.back_button(self.show_list_view)
                    title_text = "إضافة أمر تخرج جديد" if mode == "add" else f"أمر التخرج {existing_data.get('order_number', '')}"
                    ui.label(title_text).classes("app-page-title")

                # Order details, then the student linker (the page scrolls as one)
                with ui.column().classes("w-full gap-6"):
                    
                    # ── SECTION 1: Order Details Form ─────────────────────────
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("بيانات أمر التخرج").classes("app-section-title")

                        # Row 1: Order Number & Date
                        with ui.row().classes("w-full gap-4"):
                            order_num_inp = UI.text_input(
                                "رقم الأمر",
                                value=existing_data.get("order_number", "") if existing_data else "",
                                placeholder="مثال: 18515/13/2"
                            ).classes("flex-1 text-sm")

                            order_date_inp = UI.date_input(
                                "تاريخ الأمر",
                                value=existing_data.get("order_date", "") if existing_data else "",
                            ).classes("flex-1 text-sm")

                        # Row 2: Academic Details (Dept, Study Type, Year, Semester)
                        with ui.row().classes("w-full gap-4"):
                            def_dept = existing_data.get("department_id") if existing_data else (list(dept_opts.keys())[0] if dept_opts else 1)
                            dept_sel = UI.select("القسم", dept_opts, value=def_dept).classes("flex-1 text-sm")

                            def_st = existing_data.get("study_type", "morning") if existing_data else "morning"
                            st_sel = UI.select("نوع الدراسة", STUDY_TYPE_OPTIONS, value=def_st).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            # Stored as the first year (int column); shown and typed as 2025/2026
                            grad_yr_inp = UI.academic_year_input(
                                "سنة التخرج (الدفعة)",
                                value=str(existing_data.get("graduation_year", "")) if existing_data and existing_data.get("graduation_year") else "",
                            ).classes("flex-1 text-sm")

                            def_sem = existing_data.get("graduation_semester", "first") if existing_data else "first"
                            sem_sel = UI.select("فصل التخرج", SEMESTER_OPTIONS, value=def_sem).classes("flex-1 text-sm")

                        # Row 3: Student Count & Notes
                        with ui.row().classes("w-full gap-4"):
                            num_st_inp = UI.text_input(
                                "عدد الطلاب في أمر التخرج",
                                value=str(existing_data.get("num_students", "")) if existing_data and existing_data.get("num_students") else "",
                                placeholder="اختياري"
                            ).classes("flex-1 text-sm")

                            notes_inp = UI.text_input(
                                "ملاحظات",
                                value=existing_data.get("notes", "") if existing_data else "",
                                placeholder="اختياري"
                            ).classes("flex-1 text-sm")

                        # Save Order Details Button
                        with ui.row().classes("w-full justify-end gap-3 pt-2 border-t border-[var(--border-default)]"):
                            def save_order_action():
                                onum = order_num_inp.value.strip() if order_num_inp.value else ""
                                if not onum:
                                    ui.notify("رقم الأمر مطلوب", type="warning")
                                    return

                                odate_raw = order_date_inp.value.strip() if order_date_inp.value else ""
                                ok, formatted_date = validate_and_format_date(odate_raw, "تاريخ الأمر")
                                if not ok:
                                    return

                                from utils.date_parsing import academic_year_start, format_academic_year
                                gyr_start = academic_year_start(grad_yr_inp.value)
                                if not gyr_start:
                                    ui.notify("سنة التخرج مطلوبة — اكتبها مثل 2025 أو 2025/2026", type="warning")
                                    return
                                grad_yr_inp.value = format_academic_year(gyr_start)
                                gyr_str = str(gyr_start)

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
                                        ui.notify("تم إضافة أمر التخرج بنجاح", type="positive")
                                        # Switch to edit mode for newly created order so user can link students immediately
                                        payload["id"] = new_id
                                        self.show_edit_view(row=payload, mode="edit")
                                    else:
                                        self.repo.update(oid, payload)
                                        ui.notify("تم تعديل أمر التخرج بنجاح", type="positive")
                                except OfflineModeError as err:
                                    ui.notify(str(err), type="warning")
                                except Exception as err:
                                    log.error(f"Error saving order: {err}")
                                    ui.notify(f"تعذر حفظ الأمر: {err}", type="negative")

                            UI.primary_button("حفظ بيانات الأمر", icon="save", on_click=save_order_action)

                    # ── SECTION 2: students + scanned order (edit mode) ─────────
                    if mode == "edit" and oid:
                        self._build_order_workspace(oid, existing_data)

    # ── Confirm Delete ────────────────────────────────────────────────────────
    def confirm_delete(self, row: dict):
        oid = row["id"]
        order_num = row.get("order_number") or "—"
        linked_cnt = row.get("linked_count", 0) or 0

        def do_delete():
            try:
                self.repo.delete(oid)
                UI.notify(f"تم حذف الأمر ({order_num})", type="positive")
                self.show_list_view()
            except OfflineModeError as err:
                UI.notify(str(err), type="warning")
            except Exception as err:
                UI.notify(f"تعذر حذف الأمر: {err}", type="negative")

        UI.confirm_dialog(
            "حذف أمر التخرج",
            f"سيُحذف الأمر ({order_num}) ويُلغى ربط {linked_cnt} طالب به. لا يمكن التراجع عن ذلك.",
            "حذف الأمر",
            do_delete,
        )
