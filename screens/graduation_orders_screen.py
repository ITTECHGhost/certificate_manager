# =============================================================================
# screens/graduation_orders_screen.py — Graduation Orders Management Screen
# =============================================================================
#
# CHANGES:
#   - Pagination bar added (Feature 3).
#   - "View Students" button added per row (Feature 4 / Q2).
#   - Full-page form via refactored SidePanel (Feature 7).
#
# =============================================================================

import customtkinter as ctk

from config import AppFonts, AppColors, AppSizes
from data.queries import (
    get_all_orders, insert_order, update_order, delete_order,
    get_all_departments,
)
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header, make_primary_button


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

STUDY_TYPE_OPTIONS = {
    "صباحي  /  Morning": "morning",
    "مسائي  /  Evening": "evening",
}
STUDY_TYPE_DISPLAY = {v: k for k, v in STUDY_TYPE_OPTIONS.items()}

SEMESTER_OPTIONS = {
    "الفصل الأول  /  First":  "first",
    "الفصل الثاني  /  Second": "second",
}
SEMESTER_DISPLAY = {v: k for k, v in SEMESTER_OPTIONS.items()}


# =============================================================================
# Side Panel — Add / Edit a graduation order
# =============================================================================

class GraduationOrderPanel(SidePanel):
    """In-screen form panel for adding or editing a graduation order."""

    def __init__(self, parent_screen, on_save_callback) -> None:
        self._departments: list[dict] = []
        super().__init__(
            parent_screen,
            title_ar_add="إضافة أمر تخرج",   title_en_add="Add Graduation Order",
            title_ar_edit="تعديل أمر تخرج",  title_en_edit="Edit Graduation Order",
            on_save_callback=on_save_callback,
        )

    # ── Build fields ──────────────────────────────────────────────────────────

    def _build_fields(self) -> None:
        self._add_section_label("بيانات الأمر", "Order Details")
        self._order_number = self._add_entry(
            "رقم الأمر", "Order Number",
            placeholder="مثال: 18515/13/2",
            justify="left"
        )
        self._order_date = self._add_entry(
            "تاريخ الأمر", "Order Date (YYYY-MM-DD)",
            placeholder="مثال: 2024-06-15",
            justify="left"
        )

        self._add_section_label("البيانات الأكاديمية", "Academic Details")
        self._dept = self._add_dropdown("القسم", "Department", values=["—"])
        self._study_type = self._add_dropdown(
            "نوع الدراسة", "Study Type",
            values=list(STUDY_TYPE_OPTIONS.keys()),
        )
        self._admission_year = self._add_entry(
            "سنة القبول (الدفعة)", "Admission Year",
            placeholder="مثال: 2018",
            justify="left"
        )
        self._graduation_semester = self._add_dropdown(
            "فصل التخرج", "Graduation Semester",
            values=list(SEMESTER_OPTIONS.keys()),
        )

        self._add_section_label("معلومات إضافية", "Additional Info")
        self._num_students = self._add_entry(
            "عدد الطلاب (حسب الوثيقة)", "Number of Students (from document)",
            placeholder="اختياري / Optional",
            justify="left"
        )
        self._notes = self._add_entry(
            "ملاحظات", "Notes",
            placeholder="اختياري / Optional",
        )

    # ── Reload departments ────────────────────────────────────────────────────

    def _reload_departments(self) -> None:
        self._departments = get_all_departments()
        labels = [f"{d['name_ar']}  /  {d['name_en']}" for d in self._departments] or ["—"]
        self._dept.configure(values=labels)
        self._dept.set(labels[0])

    def open_add(self) -> None:
        self._reload_departments()
        super().open_add()

    def open_edit(self, data: dict) -> None:
        self._reload_departments()
        super().open_edit(data)

    # ── Populate (Edit mode) ──────────────────────────────────────────────────

    def _populate(self, data: dict) -> None:
        self._set_entry(self._order_number,    data.get("order_number", ""))
        self._set_entry(self._order_date,      data.get("order_date", ""))
        self._set_entry(self._admission_year,  str(data.get("admission_year", "")))
        self._set_entry(self._num_students,    str(data.get("num_students", "") or ""))
        self._set_entry(self._notes,           data.get("notes", "") or "")

        for d in self._departments:
            if d["id"] == data.get("department_id"):
                self._set_dropdown(self._dept, f"{d['name_ar']}  /  {d['name_en']}")
                break

        self._set_dropdown(
            self._study_type,
            STUDY_TYPE_DISPLAY.get(data.get("study_type", "morning"), ""),
        )
        self._set_dropdown(
            self._graduation_semester,
            SEMESTER_DISPLAY.get(data.get("graduation_semester", "first"), ""),
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> str | None:
        if not self._order_number.get().strip():
            return "رقم الأمر مطلوب  —  Order number is required"
        date = self._order_date.get().strip()
        if not date or len(date) != 10:
            return "تاريخ الأمر مطلوب بصيغة YYYY-MM-DD"
        if not self._departments:
            return "يجب إضافة قسم أولاً  —  Add a department first"
        if not self._admission_year.get().strip().isdigit():
            return "سنة القبول يجب أن تكون رقماً  —  Admission year must be a number"
        num = self._num_students.get().strip()
        if num and not num.isdigit():
            return "عدد الطلاب يجب أن يكون رقماً  —  Number of students must be a number"
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_dept_id(self) -> int | None:
        label = self._dept.get()
        for d in self._departments:
            if f"{d['name_ar']}  /  {d['name_en']}" == label:
                return d["id"]
        return None

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self, existing: dict | None) -> None:
        num_raw = self._num_students.get().strip()
        num_val = int(num_raw) if num_raw.isdigit() else None
        notes   = self._notes.get().strip() or None

        kwargs = dict(
            order_number        = self._order_number.get().strip(),
            order_date          = self._order_date.get().strip(),
            department_id       = self._get_dept_id(),
            study_type          = STUDY_TYPE_OPTIONS[self._study_type.get()],
            admission_year      = int(self._admission_year.get().strip()),
            graduation_semester = SEMESTER_OPTIONS[self._graduation_semester.get()],
            num_students        = num_val,
            notes               = notes,
        )
        if existing:
            update_order(order_id=existing["id"], **kwargs)
        else:
            insert_order(**kwargs)


# =============================================================================
# Screen
# =============================================================================

class GraduationOrdersScreen(BaseScreen):
    """
    Graduation Orders management screen with pagination and View Students button.
    """

    COLUMNS = [
        ("رقم الأمر  /  Order #",          130),
        ("تاريخ الأمر  /  Date",           120),
        ("القسم  /  Department",            170),
        ("الدفعة  /  Year",                  70),
        ("الدراسة  /  Type",                 80),
        ("الفصل  /  Semester",               80),
        ("طلاب مرتبطون  /  Linked",          80),
    ]

    def __init__(self, parent, switch_callback) -> None:
        self._all_rows: list[dict] = []
        self._on_view_students = None   # set by main after screen registration
        super().__init__(parent, switch_callback)

    def set_view_students_callback(self, cb) -> None:
        """Called by main.py to inject the navigation callback."""
        self._on_view_students = cb

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Panel
        self._panel = GraduationOrderPanel(self, on_save_callback=self.refresh)

        # Header row
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "أوامر التخرج", "Graduation Orders").grid(
            row=0, column=0, sticky="e"
        )
        make_primary_button(
            top, "+ إضافة أمر", "Add Order",
            command=self._panel.open_add,
        ).grid(row=0, column=1, padx=(10, 0))

        # Search bar
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(
            self,
            textvariable=self._search_var,
            placeholder_text="بحث برقم الأمر أو القسم  —  Search by order number or department...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            justify="right",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Record list — extra "View" button per row
        self._list = RecordList(
            self,
            columns=self.COLUMNS,
            on_edit=self._panel.open_edit,
            on_delete=self._confirm_delete,
            on_extra=self._view_students,
            extra_label="👁 عرض\nView",
            extra_color=AppColors.ACCENT_GREEN,
        )
        self._list.grid(row=2, column=0, sticky="nsew")

        # Pagination bar
        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def refresh(self) -> None:
        self._all_rows = get_all_orders()
        self._search_var.set("")
        self._pager.set_total(len(self._all_rows))
        self._render_page(self._all_rows)

    def _on_search(self, *_) -> None:
        term = self._search_var.get().strip().lower()
        if not term:
            filtered = self._all_rows
        else:
            filtered = [
                r for r in self._all_rows
                if term in r["order_number"].lower()
                or term in r.get("dept_name_ar", "").lower()
                or term in r.get("dept_name_en", "").lower()
                or term in str(r.get("admission_year", ""))
            ]
        self._pager.set_total(len(filtered))
        self._render_page(filtered)

    def _on_page_change(self, page: int, page_size: int) -> None:
        # Re-apply search filter and re-render
        self._on_search()

    def _render_page(self, filtered_rows: list[dict]) -> None:
        ps   = self._pager.page_size
        off  = self._pager.offset
        rows = filtered_rows[off: off + ps]
        self._list.load(rows, cell_extractor=lambda r: [
            r["order_number"],
            r["order_date"],
            r.get("dept_name_ar", "—"),
            str(r.get("admission_year", "—")),
            STUDY_TYPE_DISPLAY.get(r.get("study_type", ""), r.get("study_type", "—")),
            SEMESTER_DISPLAY.get(r.get("graduation_semester", ""), r.get("graduation_semester", "—")),
            str(r.get("linked_count", 0)),
        ])

    def _view_students(self, row: dict) -> None:
        """Navigate to the order-students sub-screen."""
        if self._on_view_students:
            self._on_view_students(row)

    def _confirm_delete(self, row: dict) -> None:
        self.show_confirm(
            message=(
                f"هل تريد حذف الأمر: {row['order_number']}؟\n"
                f"Delete order: {row['order_number']}?\n\n"
                "سيتم إلغاء ربط جميع الطلاب المرتبطين بهذا الأمر.\n"
                "All linked students will be unlinked from this order."
            ),
            on_confirm=lambda: self._delete(row),
        )

    def _delete(self, row: dict) -> None:
        delete_order(row["id"])
        self.refresh()
