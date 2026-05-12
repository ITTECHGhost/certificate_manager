# =============================================================================
# screens/courses_screen.py — Courses Management Screen
# =============================================================================
#
# CHANGES:
#   - Shared-course support: "مشتركة / Shared" checkbox in the form.
#     When checked, a multi-dept checklist appears instead of a single dropdown.
#   - Pagination added (Feature 3).
#   - Full-page form (Feature 7).
#
# =============================================================================

import customtkinter as ctk
import mysql.connector

from config import AppFonts, AppColors, AppSizes
from data.repositories import CourseRepository, DepartmentRepository, StudySystemRepository
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header, make_primary_button


# =============================================================================
# Side Panel
# =============================================================================

class CoursePanel(SidePanel):
    """Add / Edit panel for a single course (with shared-course support)."""

    def __init__(self, parent_screen, on_save_callback) -> None:
        self._departments: list[dict] = []
        self._study_systems: list[dict] = []
        self._dept_checks: list[tuple[ctk.CTkCheckBox, int]] = []
        super().__init__(
            parent_screen,
            title_ar_add="إضافة مادة",  title_en_add="Add Course",
            title_ar_edit="تعديل مادة", title_en_edit="Edit Course",
            on_save_callback=on_save_callback,
        )

    def _build_fields(self) -> None:
        self._fields_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._add_section_label("اسم المادة", "Course Name", row=0, col=3)
        self._name_ar = self._add_entry("اسم المادة بالعربية", "Arabic Course Name",
                                       placeholder="مثال: هياكل البيانات", row=0, col=1)
        self._name_en = self._add_entry("اسم المادة بالإنكليزية", "English Course Name",
                                       placeholder="e.g. Data Structures", row=0, col=0, justify="left")

        self._add_section_label("تفاصيل المادة", "Course Details", row=2, col=3)
        self._credits = self._add_dropdown("الوحدات الدراسية", "Credit Hours",
                                         values=["1","2","3","4","5","6"], row=2, col=1)
        self._stage = self._add_dropdown("المرحلة / الفصل", "Stage / Semester",
                                        values=["1","2","3","4","5","6","7","8"], row=2, col=0)
        
        self._system = self._add_dropdown("نظام الدراسة", "Study System",
                                         values=["—"], row=4, col=1)

        self._add_section_label("نطاق المادة", "Course Scope", row=4, col=3)
        self._shared_var = ctk.BooleanVar(value=False)
        self._shared_chk = ctk.CTkCheckBox(
            self._fields_frame,
            text="مادة مشتركة بين أقسام  /  Shared across departments",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            variable=self._shared_var,
            command=self._on_shared_toggle,
        )
        self._shared_chk.grid(row=4, column=0, sticky="e", pady=(32, 2)) # Adjusted pady to align with dropdown

        # Single-dept dropdown (shown when not shared)
        self._dept_label = ctk.CTkLabel(
            self._fields_frame,
            text="القسم  /  Department",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        )
        self._dept_label.grid(row=6, column=1, sticky="e", pady=(8, 2))

        self._dept = ctk.CTkOptionMenu(
            self._fields_frame,
            values=["—"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            anchor="e",
        )
        self._dept.grid(row=7, column=1, sticky="ew", pady=(0, 2))
        
        # Multi-dept checklist (shown when shared)
        self._checklist_label = ctk.CTkLabel(
            self._fields_frame,
            text="الأقسام المشتركة  /  Shared Departments",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        )
        self._checklist_label.grid(row=6, column=1, sticky="e", pady=(8, 2))

        self._dept_checklist = ctk.CTkScrollableFrame(
            self._fields_frame,
            fg_color=("gray92", "gray18"),
            height=120,
        )
        self._dept_checklist.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 2))
        self._dept_checklist.grid_columnconfigure(0, weight=1)

        # Track rows for hiding/showing
        self._dept_row = 7
        self._shared_label_row = 6
        self._checklist_row = 7

        # Start with single-dept visible
        self._dept_checklist.grid_remove()
        self._checklist_label.grid_remove()

    def _on_shared_toggle(self) -> None:
        if self._shared_var.get():
            self._dept.grid_remove()
            self._dept_label.grid_remove()
            self._dept_checklist.grid()
            self._checklist_label.grid()
        else:
            self._dept_checklist.grid_remove()
            self._checklist_label.grid_remove()
            self._dept.grid()
            self._dept_label.grid()

    def _reload_departments(self) -> None:
        self._departments = DepartmentRepository().get_all()
        labels = [f"{d['name_ar']}  /  {d['name_en']}" for d in self._departments] or ["—"]
        self._dept.configure(values=labels)
        self._dept.set(labels[0])
        # Reload study systems
        self._study_systems = StudySystemRepository().get_active()
        ss_labels = [f"{s['name_ar']}  /  {s['name_en']}" for s in self._study_systems] or ["—"]
        self._system.configure(values=ss_labels)
        if ss_labels:
            self._system.set(ss_labels[0])
        # Rebuild checklist
        for w in self._dept_checklist.winfo_children():
            w.destroy()
        self._dept_checks = []
        for i, d in enumerate(self._departments):
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                self._dept_checklist,
                text=f"{d['name_ar']}  /  {d['name_en']}",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                variable=var,
            )
            chk.grid(row=i, column=0, sticky="e", padx=4, pady=2)
            self._dept_checks.append((var, d["id"]))

    def _dept_label_for_id(self, dept_id: int) -> str:
        for d in self._departments:
            if d["id"] == dept_id:
                return f"{d['name_ar']}  /  {d['name_en']}"
        return "—"

    def _id_for_dept_label(self, label: str) -> int | None:
        for d in self._departments:
            if f"{d['name_ar']}  /  {d['name_en']}" == label:
                return d["id"]
        return None

    def open_add(self) -> None:
        self._reload_departments()
        self._shared_var.set(False)
        self._on_shared_toggle()
        super().open_add()

    def open_edit(self, data: dict) -> None:
        self._reload_departments()
        self._shared_var.set(bool(data.get("is_shared", 0)))
        self._on_shared_toggle()
        super().open_edit(data)

    def _populate(self, data: dict) -> None:
        self._set_entry(self._name_ar, data.get("name_ar", ""))
        self._set_entry(self._name_en, data.get("name_en", ""))
        self._set_dropdown(self._credits, str(data.get("credit_hours", "3")))
        self._set_dropdown(self._stage,   str(data.get("stage_number", "1")))
        # Set study system by id
        ss_id = data.get("study_system_id")
        for s in self._study_systems:
            if s["id"] == ss_id:
                self._set_dropdown(self._system, f"{s['name_ar']}  /  {s['name_en']}")
                break
        if data.get("is_shared"):
            shared_ids = CourseRepository().get_shared_dept_ids(data["id"])
            for var, did in self._dept_checks:
                var.set(did in shared_ids)
        else:
            self._set_dropdown(self._dept, self._dept_label_for_id(data.get("department_id", 0)))

    def _validate(self) -> str | None:
        if not self._departments:
            return ("يجب إضافة قسم أولاً قبل إضافة المواد.\n"
                    "Please add a department first.")
        if not self._name_ar.get().strip():
            return "اسم المادة بالعربية مطلوب  —  Arabic course name is required"
        if not self._name_en.get().strip():
            return "اسم المادة بالإنكليزية مطلوب  —  English course name is required"
        if self._shared_var.get():
            selected = [did for var, did in self._dept_checks if var.get()]
            if not selected:
                return "اختر قسماً واحداً على الأقل  —  Select at least one department"
        return None

    def _on_save(self, existing: dict | None) -> None:
        # Resolve study_system_id from dropdown label
        ss_label = self._system.get()
        ss_id = next(
            (s["id"] for s in self._study_systems
             if f"{s['name_ar']}  /  {s['name_en']}" == ss_label),
            (self._study_systems[0]["id"] if self._study_systems else 1)
        )
        is_shared  = self._shared_var.get()

        if is_shared:
            dept_id = None
            shared_ids = [did for var, did in self._dept_checks if var.get()]
        else:
            dept_id    = self._id_for_dept_label(self._dept.get())
            shared_ids = None

        kwargs = dict(
            name_ar         = self._name_ar.get().strip(),
            name_en         = self._name_en.get().strip(),
            credit_hours    = int(self._credits.get()),
            department_id   = dept_id,
            stage_number    = int(self._stage.get()),
            study_system_id = ss_id,
            shared_dept_ids = shared_ids,
        )
        repo = CourseRepository()
        if existing:
            repo.update(course_id=existing["id"], data=kwargs)
        else:
            repo.insert(data=kwargs)


# =============================================================================
# Screen
# =============================================================================

class CoursesScreen(BaseScreen):
    """
    Lists all courses with department filter + search + pagination.
    Shared courses show 'مشتركة (Dept1، Dept2)' in the department column.
    """

    COLUMNS = [
        ("اسم المادة - عربي  /  Arabic",      170),
        ("اسم المادة - إنكليزي  /  English",  170),
        ("القسم  /  Department",               180),
        ("المرحلة  /  Stage",                   60),
        ("الوحدات  /  Credits",                 60),
        ("النظام  /  System",                   80),
    ]

    ALL_DEPTS_LABEL = "كل الأقسام  —  All Departments"

    def __init__(self, parent, switch_callback) -> None:
        self._all_rows: list[dict] = []
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._panel = CoursePanel(self, on_save_callback=self.refresh)

        # Header row
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "المواد الدراسية", "Courses").grid(row=0, column=0, sticky="e")
        make_primary_button(top, "+ إضافة مادة", "Add Course",
                            command=self._panel.open_add).grid(row=0, column=1, padx=(10, 0))

        # Filter row: dept dropdown + search
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        filter_row.grid_columnconfigure(1, weight=1)

        self._dept_var = ctk.StringVar(value=self.ALL_DEPTS_LABEL)
        self._dept_var.trace_add("write", self._apply_filters)
        self._dept_menu = ctk.CTkOptionMenu(
            filter_row, variable=self._dept_var,
            values=[self.ALL_DEPTS_LABEL],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=260, height=36,
        )
        self._dept_menu.grid(row=0, column=0, padx=(0, 8))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._apply_filters)
        ctk.CTkEntry(filter_row, textvariable=self._search_var,
                     placeholder_text="بحث باسم المادة  —  Search course name...",
                     font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
                     height=36, justify="right",
                     ).grid(row=0, column=1, sticky="ew")

        # Record list
        self._list = RecordList(self, columns=self.COLUMNS,
                                on_edit=self._panel.open_edit,
                                on_delete=self._confirm_delete)
        self._list.grid(row=2, column=0, sticky="nsew")

        # Pagination bar
        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def refresh(self) -> None:
        self._all_rows = CourseRepository().get_all()
        depts = DepartmentRepository().get_all()
        dept_labels = [self.ALL_DEPTS_LABEL] + [
            f"{d['name_ar']}  /  {d['name_en']}" for d in depts
        ]
        self._dept_menu.configure(values=dept_labels)
        self._dept_var.set(self.ALL_DEPTS_LABEL)
        self._search_var.set("")
        self._pager.set_total(len(self._all_rows))
        self._render_page(self._all_rows)

    def _apply_filters(self, *_) -> None:
        dept  = self._dept_var.get()
        term  = self._search_var.get().strip().lower()
        rows  = self._all_rows

        if dept != self.ALL_DEPTS_LABEL:
            rows = [r for r in rows if dept.split("  /  ")[0] in (r.get("dept_name_ar") or "")]

        if term:
            rows = [r for r in rows
                    if term in (r.get("name_ar") or "").lower() or term in (r.get("name_en") or "").lower()]

        self._pager.set_total(len(rows))
        self._render_page(rows)

    def _on_page_change(self, page: int, page_size: int) -> None:
        self._apply_filters()

    def _render_page(self, filtered: list[dict]) -> None:
        ps   = self._pager.page_size
        off  = self._pager.offset
        rows = filtered[off: off + ps]
        self._list.load(rows, cell_extractor=lambda r: [
            r.get("name_ar") or "—",
            r.get("name_en") or "—",
            r.get("dept_name_ar") or "—",
            str(r.get("stage_number", "—")),
            str(r.get("credit_hours", "—")),
            r.get("study_system_name_ar") or "—",
        ])

    def _confirm_delete(self, row: dict) -> None:
        self.show_confirm(
            message=(f"هل تريد حذف المادة: {row['name_ar']}؟\n"
                     f"Delete course: {row['name_en']}?\n\n"
                     "لا يمكن الحذف إذا كان هناك طلاب مسجلون فيها.\n"
                     "Cannot delete if students are enrolled."),
            on_confirm=lambda: self._delete(row),
        )

    def _delete(self, row: dict) -> None:
        try:
            CourseRepository().delete(row["id"])
            self.refresh()
        except mysql.connector.Error:
            self.show_error("لا يمكن حذف هذه المادة لأن هناك طلاب مسجلون فيها.\n"
                            "Cannot delete: students are enrolled.")
