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
from data.repositories import GraduationOrderRepository, DepartmentRepository
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
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
    "الفصل الصيفي  /  Summer": "summer",
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
        self._fields_frame.grid_columnconfigure((0, 1), weight=1)

        self._add_section_label("بيانات الأمر", "Order Details", row=0, col=3, colspan=1) 
        
        self._order_number = self._add_entry(
            "رقم الأمر", "Order Number",
            placeholder="مثال: 18515/13/2",
            row=0, col=1, justify="left"
        )
        self._order_date = self._add_entry(
            "تاريخ الأمر", "Order Date (YYYY-MM-DD)",
            placeholder="مثال: 2024-06-15",
            row=0, col=0, justify="left"
        )

        self._add_section_label("البيانات الأكاديمية", "Academic Details", row=3, col=3) #, colspan=2
        
        self._dept = self._add_dropdown("القسم", "Department", values=["—"], row=6, col=1)
        self._study_type = self._add_dropdown(
            "نوع الدراسة", "Study Type",
            values=list(STUDY_TYPE_OPTIONS.keys()),
            row=6, col=0
        )
        
        self._graduation_year = self._add_entry(
            "سنة التخرج (الدفعة)", "Graduation Year",
            placeholder="مثال: 2022",
            row=6, col=2, justify="left"
        )
        self._graduation_semester = self._add_dropdown(
            "فصل التخرج", "Graduation Semester",
            values=list(SEMESTER_OPTIONS.keys()),
            row=6, col=3
        )

        self._add_section_label("معلومات إضافية", "Additional Info", row=8, col=3, colspan=1)
        
        self._num_students = self._add_entry(
            "عدد الطلاب (حسب الوثيقة)", "Number of Students (from document)",
            placeholder="اختياري / Optional",
            row=8, col=0, justify="left"
        )
        self._notes = self._add_entry(
            "ملاحظات", "Notes",
            placeholder="اختياري / Optional",
            row=8, col=1
        )

    # ── Reload departments ────────────────────────────────────────────────────

    def _reload_departments(self) -> None:
        self._departments = DepartmentRepository().get_all()
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
        self._set_entry(self._order_number,    data.get("order_number") or "")
        self._set_entry(self._order_date,      data.get("order_date") or "")
        
        grad_yr = data.get("graduation_year")
        self._set_entry(self._graduation_year,  str(grad_yr) if grad_yr is not None else "")
        
        num_stud = data.get("num_students")
        self._set_entry(self._num_students,    str(num_stud) if num_stud is not None else "")
        
        self._set_entry(self._notes,           data.get("notes") or "")

        for d in self._departments:
            if d["id"] == data.get("department_id"):
                self._set_dropdown(self._dept, f"{d['name_ar']}  /  {d['name_en']}")
                break

        st = data.get("study_type") or "morning"
        self._set_dropdown(
            self._study_type,
            STUDY_TYPE_DISPLAY.get(str(st).lower(), ""),
        )
        gs = data.get("graduation_semester") or "first"
        self._set_dropdown(
            self._graduation_semester,
            SEMESTER_DISPLAY.get(str(gs).lower(), ""),
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> str | None:
        if not self._order_number.get().strip():
            return "رقم الأمر مطلوب  —  Order number is required"
        
        from ui.widgets import normalize_date_format
        date_raw = self._order_date.get().strip()
        normalized = normalize_date_format(date_raw)
        self._set_entry(self._order_date, normalized)
        
        if not normalized or len(normalized) != 10 or "-" not in normalized:
            return "تاريخ الأمر مطلوب بصيغة YYYY-MM-DD"
        if not self._departments:
            return "يجب إضافة قسم أولاً  —  Add a department first"
        if not self._graduation_year.get().strip():
            return "سنة التخرج مطلوبة  —  Graduation year is required"
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

        grad_yr_raw = self._graduation_year.get().strip()
        try:
            grad_yr_val = int(grad_yr_raw)
        except ValueError:
            grad_yr_val = grad_yr_raw

        kwargs = dict(
            order_number        = self._order_number.get().strip(),
            order_date          = self._order_date.get().strip(),
            department_id       = self._get_dept_id(),
            study_type          = STUDY_TYPE_OPTIONS[self._study_type.get()],
            graduation_year     = grad_yr_val,
            graduation_semester = SEMESTER_OPTIONS[self._graduation_semester.get()],
            num_students        = num_val,
            notes               = notes,
        )
        repo = GraduationOrderRepository()
        if existing:
            repo.update(order_id=existing["id"], data=kwargs)
        else:
            repo.insert(data=kwargs)


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
        self.current_offset = 0
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
        top.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "أوامر التخرج", "Graduation Orders").grid(
            row=0, column=0, sticky="e"
        )
        make_primary_button(
            top, "+ إضافة أمر", "Add Order",
            command=self._panel.open_add,
        ).grid(row=0, column=1, padx=(10, 0))

        # Search bar (standardized with pady=5, padx=20)
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=5, padx=20)
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="بحث برقم الأمر أو القسم  —  Search by order number or department...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            justify="right",
        ).grid(row=0, column=0, sticky="ew")

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

        # Pagination controls
        self._pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._pagination_frame.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self._pagination_frame.grid_columnconfigure(1, weight=1)

        # Left side: Limit picker
        limit_frame = ctk.CTkFrame(self._pagination_frame, fg_color="transparent")
        limit_frame.grid(row=0, column=0, sticky="w", padx=(20, 8))

        ctk.CTkLabel(
            limit_frame,
            text="عرض  /  Show:",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        ).grid(row=0, column=0, padx=(0, 4))

        self._limit_var = ctk.StringVar(value="25")
        self._limit_menu = ctk.CTkOptionMenu(
            limit_frame,
            variable=self._limit_var,
            values=["25", "50", "75", "100"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=70,
            height=30,
            command=self._on_limit_change,
        )
        self._limit_menu.grid(row=0, column=1)

        # Centre: Nav buttons and label
        nav = ctk.CTkFrame(self._pagination_frame, fg_color="transparent")
        nav.grid(row=0, column=1)

        self._btn_prev = ctk.CTkButton(
            nav,
            text="◄  السابق",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=90,
            height=30,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._go_prev,
        )
        self._btn_prev.grid(row=0, column=0, padx=(0, 8))

        self._status_label = ctk.CTkLabel(
            nav,
            text="—",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=150,
        )
        self._status_label.grid(row=0, column=1, padx=4)

        self._btn_next = ctk.CTkButton(
            nav,
            text="التالي  ►",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=90,
            height=30,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._go_next,
        )
        self._btn_next.grid(row=0, column=2, padx=(8, 0))

    def _on_limit_change(self, *_) -> None:
        self.current_offset = 0
        self.refresh_data()

    def _go_prev(self) -> None:
        limit = int(self._limit_var.get())
        self.current_offset = max(0, self.current_offset - limit)
        self.refresh_data()

    def _go_next(self) -> None:
        limit = int(self._limit_var.get())
        self.current_offset += limit
        self.refresh_data()

    def refresh(self) -> None:
        self.current_offset = 0
        self.refresh_data()

    def refresh_data(self) -> None:
        limit = int(self._limit_var.get())
        self._all_rows = GraduationOrderRepository().get_all(limit=limit, offset=self.current_offset)
        self._search_var.set("")
        
        # Update status labels
        start_idx = self.current_offset + 1 if self._all_rows else 0
        end_idx = self.current_offset + len(self._all_rows)
        self._status_label.configure(text=f"السجلات {start_idx} - {end_idx}\nRecords {start_idx} - {end_idx}")

        # Guard Next button if we got fewer rows than limit
        if len(self._all_rows) < limit:
            self._btn_next.configure(state="disabled")
        else:
            self._btn_next.configure(state="normal")

        # Guard Prev button if offset is 0
        if self.current_offset == 0:
            self._btn_prev.configure(state="disabled")
        else:
            self._btn_prev.configure(state="normal")

        self._render_page(self._all_rows)

    def _on_search(self, *_) -> None:
        term = self._search_var.get().strip().lower()
        if not term:
            filtered = self._all_rows
        else:
            filtered = [
                r for r in self._all_rows
                if term in (r.get("order_number") or "").lower()
                or term in (r.get("dept_name_ar") or "").lower()
                or term in (r.get("dept_name_en") or "").lower()
                or term in str(r.get("graduation_year") or "")
            ]
        self._render_page(filtered)

    def _render_page(self, rows: list[dict]) -> None:
        if not self._list.winfo_exists():
            return
        self._list.load(rows, cell_extractor=lambda r: [
            r["order_number"],
            r["order_date"],
            r.get("dept_name_ar", "—"),
            str(r.get("graduation_year", "—")),
            STUDY_TYPE_DISPLAY.get(str(r.get("study_type") or "").lower(), r.get("study_type") or "—"),
            SEMESTER_DISPLAY.get(str(r.get("graduation_semester") or "").lower(), r.get("graduation_semester") or "—"),
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
        GraduationOrderRepository().delete(row["id"])
        self.refresh()
