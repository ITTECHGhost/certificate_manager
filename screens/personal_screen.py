# =============================================================================
# screens/personal_screen.py — Personnel (Signatories) Management Screen
# =============================================================================
#
# CHANGES:
#   - Edit now calls update_personal() (UPDATE in place) instead of
#     deactivate + insert.
#   - Front/Back shown as a "Page" column in one unified list (no tab).
#   - Pagination bar added.
#   - Full-page form (Feature 7) via refactored SidePanel.
#
# =============================================================================

import customtkinter as ctk

from config import AppFonts, AppColors
from data.queries import (
    get_all_personal, insert_personal, update_personal, deactivate_personal,
)
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header, make_primary_button


# =============================================================================
# Side Panel
# =============================================================================

class PersonalPanel(SidePanel):
    """Add / Edit panel for a single signatory."""

    PAGE_OPTIONS = {
        "وجه الوثيقة  /  Front Page (1-4)": "front",
        "ظهر الوثيقة  /  Back Page  (5-6)": "back",
    }
    PAGE_DISPLAY = {v: k for k, v in PAGE_OPTIONS.items()}

    def __init__(self, parent_screen, on_save_callback) -> None:
        super().__init__(
            parent_screen,
            title_ar_add="إضافة كادر",  title_en_add="Add Signatory",
            title_ar_edit="تعديل كادر", title_en_edit="Edit Signatory",
            on_save_callback=on_save_callback,
        )

    def _build_fields(self) -> None:
        self._add_section_label("الاسم", "Name")
        self._name_ar   = self._add_entry("الاسم بالعربية",    "Arabic Name",
                                           placeholder="مثال: رائدة سالم خضير")
        self._name_en   = self._add_entry("الاسم بالإنكليزية", "English Name",
                                           placeholder="e.g. Raeda Salem Khudhair")

        self._add_section_label("اللقب الأكاديمي", "Academic Title")
        self._title_ar  = self._add_entry("اللقب بالعربية",    "Arabic Title",
                                           placeholder="مثال: الأستاذ الدكتور")
        self._title_en  = self._add_entry("اللقب بالإنكليزية", "English Title",
                                           placeholder="e.g. Prof. Dr.")

        self._add_section_label("المنصب والموقع", "Role & Position")
        self._resp_ar   = self._add_entry("المنصب بالعربية",    "Arabic Responsibility",
                                           placeholder="مثال: معاون العميد للشؤون العلمية")
        self._resp_en   = self._add_entry("المنصب بالإنكليزية", "English Responsibility",
                                           placeholder="e.g. Vice Dean for Academic Affairs")

        self._add_section_label("الموقع في الوثيقة", "Document Position")
        self._page      = self._add_dropdown("صفحة التوقيع", "Signature Page",
                                              values=list(self.PAGE_OPTIONS.keys()))
        self._order     = self._add_dropdown("ترتيب التوقيع", "Signature Order",
                                              values=["1", "2", "3", "4", "5", "6"])

    def _populate(self, data: dict) -> None:
        self._set_entry(self._name_ar,  data.get("name_ar",           ""))
        self._set_entry(self._name_en,  data.get("name_en",           ""))
        self._set_entry(self._title_ar, data.get("academic_title_ar", ""))
        self._set_entry(self._title_en, data.get("academic_title_en", ""))
        self._set_entry(self._resp_ar,  data.get("responsibility_ar", ""))
        self._set_entry(self._resp_en,  data.get("responsibility_en", ""))
        self._set_dropdown(self._page,
                           self.PAGE_DISPLAY.get(data.get("page_location", "front"), ""))
        self._set_dropdown(self._order, str(data.get("display_order", "1")))

    def _validate(self) -> str | None:
        if not self._name_ar.get().strip():
            return "الاسم بالعربية مطلوب  —  Arabic name is required"
        if not self._name_en.get().strip():
            return "الاسم بالإنكليزية مطلوب  —  English name is required"
        if not self._resp_ar.get().strip():
            return "المنصب بالعربية مطلوب  —  Arabic responsibility is required"
        return None

    def _on_save(self, existing: dict | None) -> None:
        """
        Edit → UPDATE the existing row in place (no new row created).
        Add  → INSERT a new row.
        Both paths write to the audit log via the query layer.
        """
        kwargs = dict(
            name_ar           = self._name_ar.get().strip(),
            name_en           = self._name_en.get().strip(),
            academic_title_ar = self._title_ar.get().strip(),
            academic_title_en = self._title_en.get().strip(),
            responsibility_ar = self._resp_ar.get().strip(),
            responsibility_en = self._resp_en.get().strip(),
            display_order     = int(self._order.get()),
            page_location     = self.PAGE_OPTIONS[self._page.get()],
        )
        if existing:
            update_personal(person_id=existing["id"], **kwargs)
        else:
            insert_personal(**kwargs)


# =============================================================================
# Screen
# =============================================================================

class PersonalScreen(BaseScreen):
    """
    Lists all signatories — front AND back — in one unified paginated list.
    The Page column shows وجه / Front or ظهر / Back.
    """

    COLUMNS = [
        ("الاسم  /  Name",            160),
        ("اللقب  /  Title",            130),
        ("المنصب  /  Responsibility",  220),
        ("الصفحة  /  Page",             80),
        ("الترتيب  /  Order",           60),
        ("الحالة  /  Status",           80),
    ]

    def __init__(self, parent, switch_callback) -> None:
        self._all_rows: list[dict] = []
        self._page      = 1
        self._page_size = 25
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._panel = PersonalPanel(self, on_save_callback=self.refresh)

        # Header row: title + Add button
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(1, weight=1)

        make_primary_button(top, "+ إضافة كادر", "Add Signatory",
                            command=self._panel.open_add
                            ).grid(row=0, column=0)

        make_section_header(top, "الكوادر", "Personal").grid(
            row=0, column=1, sticky="e", padx=(10, 0)
        )

        # Record list
        self._list = RecordList(self, columns=self.COLUMNS,
                                on_edit=self._panel.open_edit,
                                on_delete=self._confirm_deactivate)
        self._list.grid(row=2, column=0, sticky="nsew")

        # Pagination bar
        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def refresh(self) -> None:
        self._all_rows = get_all_personal()
        self._page = 1
        self._pager.set_total(len(self._all_rows))
        self._render_page()

    def _on_page_change(self, page: int, page_size: int) -> None:
        self._page      = page
        self._page_size = page_size
        self._render_page()

    def _render_page(self) -> None:
        ps   = self._pager.page_size
        off  = self._pager.offset
        rows = self._all_rows[off: off + ps]
        self._list.load(rows, cell_extractor=lambda r: [
            r["name_ar"],
            r["academic_title_ar"],
            r["responsibility_ar"],
            "وجه / Front" if r["page_location"] == "front" else "ظهر / Back",
            str(r["display_order"]),
            "✅ نشط" if r["is_active"] else "⛔ غير نشط",
        ])

    def _confirm_deactivate(self, row: dict) -> None:
        if not row["is_active"]:
            self.show_error("هذا الكادر غير نشط بالفعل.\nThis person is already inactive.")
            return
        self.show_confirm(
            message=(f"هل تريد إلغاء تفعيل: {row['name_ar']}؟\n"
                     f"Deactivate: {row['name_en']}?\n\n"
                     "لن يظهر في الوثائق الجديدة لكن سيبقى السجل محفوظاً.\n"
                     "Won't appear on new certificates but the record is kept."),
            on_confirm=lambda: self._deactivate(row),
        )

    def _deactivate(self, row: dict) -> None:
        deactivate_personal(row["id"])
        self.refresh()
