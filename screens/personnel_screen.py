import customtkinter as ctk

from config import AppFonts, AppColors, AppSizes
from data.queries import (
    get_all_personnel, insert_personnel, update_personnel, 
    deactivate_personnel, activate_personnel, delete_personnel
)
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.record_list import RecordList
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header, make_primary_button

class PersonnelPanel(SidePanel):
    ORDER_OPTIONS = {
        "1": (1, "front"),
        "2": (2, "front"),
        "3": (3, "front"),
        "4": (4, "front"),
        "5": (5, "back"),
        "6": (6, "back"),
        "7": (7, "back"),
        "8": (8, "back"),
        "9": (9, "back"),
        "10": (10, "back"),
        "بدون / None": (None, None),
    }
    ORDER_REVERSE = {v: k for k, v in ORDER_OPTIONS.items()}
    ROLE_OPTIONS = ["user", "admin"]

    def __init__(self, parent_screen, on_save_callback) -> None:
        super().__init__(
            parent_screen,
            title_ar_add="إضافة مستخدم/كادر",  title_en_add="Add Personnel",
            title_ar_edit="تعديل مستخدم/كادر", title_en_edit="Edit Personnel",
            on_save_callback=on_save_callback,
        )

    def _build_fields(self) -> None:
        self._fields_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # -- ROW 0: Account Details --
        self._add_section_label("حساب الدخول", "Account Details", row=0, col=3)

        self._username = self._add_entry("اسم المستخدم", "Username", placeholder="e.g. admin", row=0, col=0, justify="left")
        
        # Manually build password field with eye button
        row = 0
        col = 1
        ctk.CTkLabel(
            self._fields_frame,
            text="كلمة المرور  /  Password",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=row, column=col, sticky="e", pady=(8, 2), padx=10)

        pass_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        pass_frame.grid(row=row+1, column=col, sticky="ew", pady=(0, 2), padx=10)
        pass_frame.grid_columnconfigure(0, weight=1)

        self._password = ctk.CTkEntry(
            pass_frame,
            placeholder_text="********",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            justify="left",
            show="*"
        )
        self._password.grid(row=0, column=0, sticky="ew")

        self._show_pass = False
        self._eye_btn = ctk.CTkButton(
            pass_frame,
            text="👁",
            width=36,
            height=36,
            command=self._toggle_password,
            fg_color="gray70", hover_color="gray60"
        )
        self._eye_btn.grid(row=0, column=1, padx=(5, 0))

        self._role = self._add_dropdown("الصلاحية", "Role", values=self.ROLE_OPTIONS, row=0, col=2)

        # -- ROW 3: Personal Information --
        self._add_section_label("المعلومات الشخصية", "Personal Information", row=3, col=3)

        self._name_ar  = self._add_entry("الاسم بالعربية", "Arabic Name", placeholder="مثال: رائدة سالم", row=3, col=1)
        self._title_ar = self._add_entry("اللقب بالعربية", "Arabic Title", placeholder="مثال: أستاذ", row=3, col=2)
        self._name_en  = self._add_entry("الاسم بالإنكليزية", "English Name", placeholder="e.g. Raeda Salem", row=3, col=0, justify="left")

        self._title_en = self._add_entry("اللقب بالإنكليزية", "English Title", placeholder="e.g. Prof. Dr.", row=5, col=0, justify="left")
        self._resp_ar  = self._add_entry("المنصب بالعربية", "Arabic Resp.", placeholder="معاون العميد", row=5, col=1)
        self._resp_en  = self._add_entry("المنصب بالإنكليزية", "English Resp.", placeholder="Vice Dean", row=5, col=2, justify="left")

        # -- ROW 8: Document Position Header --
        self._add_section_label("الموقع في الوثيقة", "Document Position", row=8, col=3)

        self._pos_dropdown = self._add_dropdown(
            "الموقع في الوثيقة", "Document Position", 
            values=list(self.ORDER_OPTIONS.keys()), 
            row=8, col=0, colspan=1
        )

        # -- NEW FIELDS: Signature --
        self._add_section_label("إعدادات الوثيقة", "Certificate Mapping", row=11, col=3)

        self._is_signature = ctk.CTkCheckBox(
            self._fields_frame,
            text="يظهر كتوقيع في الوثيقة  /  Is Signature",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
        )
        self._is_signature.grid(row=12, column=0, sticky="w", padx=10, pady=10)

    def _toggle_password(self):
        self._show_pass = not self._show_pass
        self._password.configure(show="" if self._show_pass else "*")

    def _populate(self, data: dict) -> None:
        self._set_entry(self._username, data.get("username", ""))
        self._set_entry(self._password, data.get("password", ""))
        self._set_dropdown(self._role, data.get("role", "user"))
        self._set_entry(self._name_ar,  data.get("name_ar",           ""))
        self._set_entry(self._name_en,  data.get("name_en",           ""))
        self._set_entry(self._title_ar, data.get("academic_title_ar", ""))
        self._set_entry(self._title_en, data.get("academic_title_en", ""))
        self._set_entry(self._resp_ar,  data.get("responsibility_ar", ""))
        self._set_entry(self._resp_en,  data.get("responsibility_en", ""))
        order = data.get("display_order")
        page  = data.get("page_location")
        display_str = self.ORDER_REVERSE.get((order, page), "بدون / None")
        self._set_dropdown(self._pos_dropdown, display_str)
        
        if data.get("is_signature"):
            self._is_signature.select()
        else:
            self._is_signature.deselect()

    def _validate(self) -> str | None:
        if not self._name_ar.get().strip():
            return "الاسم بالعربية مطلوب  —  Arabic name is required"
        return None

    def _on_save(self, existing: dict | None) -> None:
        kwargs = dict(
            username          = self._username.get().strip() or None,
            password          = self._password.get().strip() or None,
            role              = self._role.get(),
            name_ar           = self._name_ar.get().strip(),
            name_en           = self._name_en.get().strip(),
            academic_title_ar = self._title_ar.get().strip(),
            academic_title_en = self._title_en.get().strip(),
            responsibility_ar = self._resp_ar.get().strip(),
            responsibility_en = self._resp_en.get().strip(),
            display_order     = self.ORDER_OPTIONS[self._pos_dropdown.get()][0],
            page_location     = self.ORDER_OPTIONS[self._pos_dropdown.get()][1],
            is_signature      = 1 if self._is_signature.get() else 0,
            template_appearance_id = existing.get("template_appearance_id") if existing else None,
        )
        if existing:
            update_personnel(person_id=existing["id"], **kwargs)
        else:
            insert_personnel(**kwargs)

class PersonnelScreen(BaseScreen):
    COLUMNS = [
        ("الاسم  /  Name",            160),
        ("المستخدم  /  User",         100),
        ("اللقب  /  Title",           100),
        ("المنصب  /  Pos",            140),
        ("التسلسل  /  Order",         60),
        ("توقيع  /  Sig",              80),
        ("الحالة  /  State",           80),
    ]

    def __init__(self, parent, switch_callback) -> None:
        self._all_rows: list[dict] = []
        self._page      = 1
        self._page_size = 25
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._panel = PersonnelPanel(self, on_save_callback=self.refresh)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        top.grid_columnconfigure(0, weight=1) # Allow space between Add button and Title

        make_primary_button(top, "+ إضافة كادر", "Add Personnel",
                            command=self._panel.open_add
                            ).grid(row=0, column=0, sticky="w")

        make_section_header(top, "المستخدمون والكوادر", "Personnel Management").grid(
            row=0, column=1, sticky="e", padx=(10, 0)
        )

        self._list = RecordList(self, columns=self.COLUMNS,
                                on_edit=self._panel.open_edit,
                                on_delete=self._handle_delete_click,
                                on_cell_click=self._handle_cell_click,
                                is_rtl=True)
        self._list.grid(row=2, column=0, sticky="nsew")

        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def refresh(self) -> None:
        self._all_rows = get_all_personnel()
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
            r.get("username", "-") or "-",
            r.get("academic_title_ar", "-") or "-",
            r.get("responsibility_ar", "-") or "-",
            str(r.get("display_order")) if r.get("display_order") else "-",
            "🖋️ نعم / Yes" if r.get("is_signature") else "❌ لا / No",
            "✅ نشط / Active" if r.get("is_active") else "⛔ معطل / Inactive",
        ])

    def _handle_cell_click(self, row: dict, col_idx: int) -> None:
        if col_idx == 5: # Is Signature
            new_val = 0 if row.get("is_signature") else 1
            # If turning off signature, also clear order
            update_personnel(
                person_id=row["id"],
                name_ar=row["name_ar"], name_en=row["name_en"],
                username=row["username"], password=row["password"],
                role=row["role"], academic_title_ar=row["academic_title_ar"],
                academic_title_en=row["academic_title_en"],
                responsibility_ar=row["responsibility_ar"],
                responsibility_en=row["responsibility_en"],
                display_order=row["display_order"] if new_val else None,
                page_location=row["page_location"] if new_val else None,
                is_signature=new_val,
                template_appearance_id=row.get("template_appearance_id")
            )
            self.refresh()
        elif col_idx == 6: # State
            if row.get("is_active"):
                deactivate_personnel(row["id"])
            else:
                activate_personnel(row["id"])
            self.refresh()

    def _handle_delete_click(self, row: dict) -> None:
        warning = ""
        if row.get("is_active"):
            warning = "تحذير: هذا الكادر لا يزال نشطاً.\n"
        self.show_confirm(
            message=f"{warning}هل أنت متأكد من حذف هذا السجل نهائياً؟\n{row['name_ar']}",
            on_confirm=lambda: self._delete(row),
        )

    def _delete(self, row: dict) -> None:
        try:
            delete_personnel(row["id"])
            self.refresh()
        except Exception as e:
            self.show_error(f"Cannot delete record. {e}")
