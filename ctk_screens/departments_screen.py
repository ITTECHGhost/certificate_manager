# =============================================================================
# ctk_screens/departments_screen.py — Departments Management Screen (CustomTkinter)
# =============================================================================

import customtkinter as ctk
import mysql.connector

from config import AppFonts
from data.repositories import DepartmentRepository
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header, make_primary_button


# =============================================================================
# Side Panel
# =============================================================================

class DepartmentPanel(SidePanel):
    """Add / Edit panel for a single department."""

    def __init__(self, parent_screen, on_save_callback) -> None:
        super().__init__(
            parent_screen,
            title_ar_add="إضافة قسم",  title_en_add="Add Department",
            title_ar_edit="تعديل قسم", title_en_edit="Edit Department",
            on_save_callback=on_save_callback,
        )

    def _build_fields(self) -> None:
        self._fields_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._add_section_label("معلومات القسم", "Department Info", row=0, col=3)
        
        self._name_ar = self._add_entry("اسم القسم بالعربية", "Arabic Name",
                                       placeholder="مثال: قسم علوم الحاسوب", row=0, col=1)
        self._name_en = self._add_entry("اسم القسم بالإنكليزية", "English Name",
                                       placeholder="e.g. Computer Science", row=0, col=0, justify="left")
        
        self._college_ar = self._add_entry("اسم الكلية بالعربية", "Arabic College Name",
                                          placeholder="مثال: كلية التقنية المعلوماتية", row=0, col=2)
        
        self._add_section_label("معلومات الكلية", "College Info", row=2, col=3)
        self._college_en = self._add_entry("اسم الكلية بالإنكليزية", "English College Name",
                                          placeholder="e.g. IT College", row=2, col=0, justify="left")
        self._college_ar = self._add_entry("اسم الكلية بالعربية", "Arabic College Name",
                                          placeholder="مثال: كلية التقنية", row=2, col=1)

    def _populate(self, data: dict) -> None:
        self._set_entry(self._name_ar,    data.get("name_ar",    ""))
        self._set_entry(self._name_en,    data.get("name_en",    ""))
        self._set_entry(self._college_ar, data.get("college_name_ar") or data.get("college_ar") or "")
        self._set_entry(self._college_en, data.get("college_name_en") or data.get("college_en") or "")

    def _validate(self) -> str | None:
        if not self._name_ar.get().strip():
            return "اسم القسم بالعربية مطلوب  —  Arabic name is required"
        if not self._name_en.get().strip():
            return "اسم القسم بالإنكليزية مطلوب  —  English name is required"
        if not self._college_ar.get().strip():
            return "اسم الكلية بالعربية مطلوب  —  Arabic college name is required"
        if not self._college_en.get().strip():
            return "اسم الكلية بالإنكليزية مطلوب  —  English college name is required"
        return None

    def _on_save(self, existing: dict | None) -> None:
        kwargs = dict(
            name_ar    = self._name_ar.get().strip(),
            name_en    = self._name_en.get().strip(),
            college_ar = self._college_ar.get().strip(),
            college_en = self._college_en.get().strip(),
        )
        repo = DepartmentRepository()
        if existing:
            repo.update(dept_id=existing["id"], **kwargs)
        else:
            repo.insert(**kwargs)


# =============================================================================
# Screen
# =============================================================================

class DepartmentsScreen(BaseScreen):
    """
    Lists all departments with search, add, edit, and delete.
    """

    COLUMNS = [
        ("اسم القسم - عربي  /  Arabic Name",    200),
        ("اسم القسم - إنكليزي  /  English Name", 200),
        ("الكلية  /  College",                    220),
    ]

    def __init__(self, parent, switch_callback) -> None:
        self._all_rows: list[dict] = []
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._panel = DepartmentPanel(self, on_save_callback=self.refresh)

        # Header row
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "الأقسام", "Departments").grid(row=0, column=0, sticky="e")
        make_primary_button(top, "+ إضافة قسم", "Add Department",
                            command=self._panel.open_add).grid(row=0, column=1, padx=(10, 0))

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=5, padx=20)
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(search_frame, textvariable=self._search_var,
                     placeholder_text="بحث بالاسم  —  Search by name...",
                     font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
                     height=36, justify="right"
                     ).grid(row=0, column=0, sticky="ew")

        # Record list
        self._list = RecordList(self, columns=self.COLUMNS,
                                on_edit=self._panel.open_edit,
                                on_delete=self._confirm_delete)
        self._list.grid(row=2, column=0, sticky="nsew")

        # Pagination bar
        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def refresh(self) -> None:
        repo = DepartmentRepository()
        self._all_rows = repo.get_all()
        self._search_var.set("")
        self._pager.set_total(len(self._all_rows))
        self._render_page(self._all_rows)

    def _on_page_change(self, page: int, page_size: int) -> None:
        self._on_search()

    def _render_page(self, filtered: list[dict]) -> None:
        ps   = self._pager.page_size
        off  = self._pager.offset
        rows = filtered[off: off + ps]
        self._list.load(rows, cell_extractor=lambda r: [
            r.get("name_ar") or "",
            r.get("name_en") or "",
            r.get("college_name_ar") or r.get("college_ar") or ""
        ])

    def _render_list(self, rows: list[dict]) -> None:
        self._render_page(rows)

    def _on_search(self, *_) -> None:
        term = self._search_var.get().strip().lower()
        filtered = self._all_rows if not term else [
            r for r in self._all_rows
            if term in (r.get("name_ar") or "").lower()
            or term in (r.get("name_en") or "").lower()
            or term in (r.get("college_name_ar") or r.get("college_ar") or "").lower()
        ]

        self._pager.set_total(len(filtered))
        self._render_page(filtered)

    def _confirm_delete(self, row: dict) -> None:
        self.show_confirm(
            message=(f"هل تريد حذف قسم: {row['name_ar']}؟\n"
                     f"Delete department: {row['name_en']}?\n\n"
                     "لا يمكن الحذف إذا كان هناك طلاب أو مواد مرتبطة.\n"
                     "Cannot delete if students or courses are linked."),
            on_confirm=lambda: self._delete(row),
        )

    def _delete(self, row: dict) -> None:
        try:
            repo = DepartmentRepository()
            repo.delete(row["id"])
            self.refresh()
        except mysql.connector.Error:
            self.show_error("لا يمكن حذف هذا القسم لأن هناك طلاب أو مواد مرتبطة به.\n"
                            "Cannot delete: students or courses are linked.")
