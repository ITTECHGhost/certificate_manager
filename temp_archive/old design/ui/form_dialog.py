# =============================================================================
# ui/form_dialog.py — Reusable Modal Form Dialog Base Class
# =============================================================================
#
# PURPOSE:
#   All Add / Edit forms in the application (departments, courses, personal,
#   students) share the same modal dialog structure. This base class provides
#   that structure so each form only writes its own unique fields.
#
# HOW TO USE:
#   Subclass FormDialog and implement:
#       _build_fields(self)  → add your CTkEntry / CTkOptionMenu widgets
#       _get_values(self)    → return a dict of field_name → value
#       _validate(self)      → return error message str, or None if valid
#       _on_save(self)       → call the appropriate queries.py function
#
# WHAT THIS BASE CLASS PROVIDES:
#   • Modal window setup (grab_set, centered, fixed size)
#   • Bilingual title bar
#   • Scrollable field area
#   • Save / Cancel button row
#   • Error display inside the dialog (no separate popup for field errors)
#
# =============================================================================

import customtkinter as ctk
from abc import ABC, abstractmethod
from config import AppFonts, AppColors, AppSizes


class FormDialog(ctk.CTkToplevel, ABC):
    """
    Abstract base class for all Add / Edit form dialogs.

    Subclass template:
    ------------------
        class AddDepartmentDialog(FormDialog):

            def __init__(self, parent, on_save):
                super().__init__(parent, "إضافة قسم", "Add Department", on_save)

            def _build_fields(self) -> None:
                self._name_ar = self._add_entry("الاسم بالعربية", "Arabic Name")
                self._name_en = self._add_entry("الاسم بالإنكليزية", "English Name")

            def _validate(self) -> str | None:
                if not self._name_ar.get().strip():
                    return "الاسم بالعربية مطلوب  —  Arabic name is required"
                return None

            def _on_save(self) -> None:
                insert_department(
                    name_ar=self._name_ar.get().strip(),
                    name_en=self._name_en.get().strip(),
                )
    """

    # Default dialog dimensions — subclasses may override
    DIALOG_WIDTH  = 500
    DIALOG_HEIGHT = 480

    def __init__(
        self,
        parent,
        title_ar: str,
        title_en: str,
        on_save_callback,           # Callable[[], None] — called after save
    ) -> None:
        """
        Args:
            parent:            The parent window or frame.
            title_ar:          Dialog title in Arabic.
            title_en:          Dialog title in English.
            on_save_callback:  Called with no arguments after a successful save.
                               Use this to refresh the calling screen.
        """
        super().__init__(parent)
        self._on_save_callback = on_save_callback

        self._setup_window(title_ar, title_en)
        self._build_header(title_ar, title_en)
        self._build_field_area()
        self._build_fields()            # subclass fills in the fields
        self._build_button_row()
        self._error_label: ctk.CTkLabel | None = None

    # -------------------------------------------------------------------------
    # Window setup
    # -------------------------------------------------------------------------

    def _setup_window(self, title_ar: str, title_en: str) -> None:
        """Configure the dialog window."""
        self.title(f"{title_ar}  —  {title_en}")
        self.geometry(f"{self.DIALOG_WIDTH}x{self.DIALOG_HEIGHT}")
        self.resizable(False, False)
        self.grab_set()                 # make modal — blocks parent window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def _build_header(self, title_ar: str, title_en: str) -> None:
        """Bilingual title at the top of the dialog."""
        header = ctk.CTkFrame(
            self,
            height=52,
            corner_radius=0,
            fg_color=AppColors.HEADER_BG,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text=f"{title_ar}  —  {title_en}",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SUBHEADING,
                weight="bold",
            ),
            anchor="center",
        ).grid(row=0, column=0, pady=12)

    def _build_field_area(self) -> None:
        """
        Scrollable area that holds all form fields.
        Subclasses add widgets into self._fields_frame.
        """
        self._fields_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._fields_frame.grid(
            row=1, column=0, sticky="nsew", padx=20, pady=(14, 0)
        )
        self._fields_frame.grid_columnconfigure(0, weight=1)
        self._field_row = 0             # internal row counter

    def _build_button_row(self) -> None:
        """Save and Cancel buttons at the bottom of the dialog."""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=14, padx=20, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        # Save button
        ctk.CTkButton(
            btn_frame,
            text="حفظ  /  Save",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=160,
            height=38,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._handle_save,
        ).grid(row=0, column=1, padx=(6, 0))

        # Cancel button
        ctk.CTkButton(
            btn_frame,
            text="إلغاء  /  Cancel",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=160,
            height=38,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color="gray60",
            hover_color="gray50",
            command=self.destroy,
        ).grid(row=0, column=0, padx=(0, 6))

    # -------------------------------------------------------------------------
    # Field helpers — subclasses call these inside _build_fields()
    # -------------------------------------------------------------------------

    def _add_entry(
        self,
        label_ar: str,
        label_en: str,
        placeholder: str = "",
        initial_value: str = "",
    ) -> ctk.CTkEntry:
        """
        Add a labeled text entry field to the form.

        Args:
            label_ar:      Arabic field label.
            label_en:      English field label.
            placeholder:   Hint text shown when field is empty.
            initial_value: Pre-filled text (used when editing).

        Returns:
            The CTkEntry widget for reading its value later.
        """
        ctk.CTkLabel(
            self._fields_frame,
            text=f"{label_ar}  /  {label_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=self._field_row, column=0, sticky="e", pady=(8, 2))
        self._field_row += 1

        entry = ctk.CTkEntry(
            self._fields_frame,
            placeholder_text=placeholder,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
        )
        entry.grid(row=self._field_row, column=0, sticky="ew", pady=(0, 4))
        self._field_row += 1

        if initial_value:
            entry.insert(0, initial_value)

        return entry

    def _add_dropdown(
        self,
        label_ar: str,
        label_en: str,
        values: list[str],
        initial_value: str = "",
    ) -> ctk.CTkOptionMenu:
        """
        Add a labeled dropdown (OptionMenu) to the form.

        Args:
            label_ar:      Arabic field label.
            label_en:      English field label.
            values:        List of string choices.
            initial_value: Pre-selected value (used when editing).

        Returns:
            The CTkOptionMenu widget for reading its value later.
        """
        ctk.CTkLabel(
            self._fields_frame,
            text=f"{label_ar}  /  {label_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=self._field_row, column=0, sticky="e", pady=(8, 2))
        self._field_row += 1

        dropdown = ctk.CTkOptionMenu(
            self._fields_frame,
            values=values,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
        )
        dropdown.grid(row=self._field_row, column=0, sticky="ew", pady=(0, 4))
        self._field_row += 1

        if initial_value and initial_value in values:
            dropdown.set(initial_value)
        elif values:
            dropdown.set(values[0])

        return dropdown

    def _add_section_label(self, text_ar: str, text_en: str) -> None:
        """Add a visual section separator with a bilingual heading."""
        # Divider line
        ctk.CTkFrame(
            self._fields_frame,
            height=1,
            fg_color=AppColors.DIVIDER,
        ).grid(row=self._field_row, column=0, sticky="ew", pady=(12, 0))
        self._field_row += 1

        ctk.CTkLabel(
            self._fields_frame,
            text=f"{text_ar}  —  {text_en}",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SMALL,
                weight="bold",
            ),
            anchor="e",
        ).grid(row=self._field_row, column=0, sticky="e", pady=(4, 4))
        self._field_row += 1

    # -------------------------------------------------------------------------
    # Save flow
    # -------------------------------------------------------------------------

    def _handle_save(self) -> None:
        """
        Orchestrate the save flow:
            1. Clear any previous error message
            2. Run _validate() — show error and abort if invalid
            3. Run _on_save() — call the data layer
            4. Call on_save_callback to refresh the parent screen
            5. Close the dialog
        """
        self._clear_error()

        error = self._validate()
        if error:
            self._show_inline_error(error)
            return

        try:
            self._on_save()
            self._on_save_callback()
            self.destroy()
        except Exception as e:
            self._show_inline_error(f"خطأ في الحفظ  —  Save error:\n{e}")

    def _show_inline_error(self, message: str) -> None:
        """Show an error message inside the dialog (below the fields)."""
        if self._error_label:
            self._error_label.destroy()

        self._error_label = ctk.CTkLabel(
            self._fields_frame,
            text=f"⚠️  {message}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            text_color=AppColors.COLOR_ERROR,
            wraplength=420,
            justify="right",
            anchor="e",
        )
        self._error_label.grid(
            row=self._field_row, column=0, sticky="e", pady=(8, 0)
        )

    def _clear_error(self) -> None:
        """Remove the inline error label if one is displayed."""
        if self._error_label:
            self._error_label.destroy()
            self._error_label = None

    # -------------------------------------------------------------------------
    # Abstract methods — subclasses MUST implement
    # -------------------------------------------------------------------------

    @abstractmethod
    def _build_fields(self) -> None:
        """
        Add all form fields using self._add_entry() and self._add_dropdown().
        Store the returned widgets as instance attributes so _on_save() can
        read their values.
        """

    @abstractmethod
    def _validate(self) -> str | None:
        """
        Validate all fields before saving.

        Returns:
            None if all fields are valid.
            A bilingual error string if validation fails.
        """

    @abstractmethod
    def _on_save(self) -> None:
        """
        Write the form data to the database.
        Call the appropriate function from data/queries.py.
        Do NOT call self.destroy() here — the base class handles that.
        """
