# =============================================================================
# ui/side_panel.py — Full-Page Add/Edit Form
# =============================================================================
#
# CHANGE (Feature 7):
#   Forms no longer split the screen in half.  When opened the panel hides
#   the sibling list column and expands to fill the full screen width.
#   A ← back arrow in the header restores the list.
#
# HOW IT WORKS:
#   _show()  → grid_remove() every sibling widget in the parent frame,
#              then grid() self spanning the full width (col 0, col span)
#   close()  → grid_remove() self, grid() siblings back
#
# HOW TO SUBCLASS:
#   class DepartmentPanel(SidePanel):
#       def _build_fields(self) -> None: ...
#       def _populate(self, data: dict) -> None: ...
#       def _validate(self) -> str | None: ...
#       def _on_save(self, existing: dict | None) -> None: ...
#
# =============================================================================

import customtkinter as ctk
from abc import ABC, abstractmethod
from config import AppFonts, AppColors, AppSizes


class SidePanel(ctk.CTkFrame, ABC):
    """
    Abstract base class for all in-screen Add/Edit panels.
    Subclasses implement _build_fields, _populate, _validate, _on_save.
    """

    PANEL_WIDTH = 700     # max width in full-page mode (capped by window)

    def __init__(
        self,
        parent_screen: ctk.CTkFrame,
        title_ar_add: str,
        title_en_add: str,
        title_ar_edit: str,
        title_en_edit: str,
        on_save_callback,           # Callable[[], None]
    ) -> None:
        super().__init__(
            parent_screen,
            corner_radius=0,
            border_width=0,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._parent           = parent_screen
        self._on_save_callback = on_save_callback
        self._title_ar_add     = title_ar_add
        self._title_en_add     = title_en_add
        self._title_ar_edit    = title_ar_edit
        self._title_en_edit    = title_en_edit
        self._existing: dict | None = None
        self._field_row        = 0
        self._error_label: ctk.CTkLabel | None = None

        # Keep track of siblings we hide when the form opens
        self._hidden_siblings: list[ctk.CTkBaseClass] = []

        self._build_header()
        self._build_scroll_area()
        self._build_fields()            # subclass fills in the fields
        self._build_buttons()

    # =========================================================================
    # Layout construction
    # =========================================================================

    def _build_header(self) -> None:
        """Top bar with ← back arrow and bilingual title."""
        header = ctk.CTkFrame(
            self,
            height=52,
            corner_radius=0,
            fg_color=AppColors.HEADER_BG,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # ← Back button (left side)
        ctk.CTkButton(
            header,
            text="←  رجوع  /  Back",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=130,
            height=36,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color="transparent",
            hover_color=AppColors.NAV_HOVER_BG,
            text_color=AppColors.NAV_TEXT,
            anchor="w",
            command=self.close,
        ).grid(row=0, column=0, sticky="w", padx=(12, 0), pady=8)

        # Title label (right side)
        self._title_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SUBHEADING,
                weight="bold",
            ),
            anchor="e",
        )
        self._title_label.grid(row=0, column=1, sticky="e", padx=(0, 20), pady=12)

    def _build_scroll_area(self) -> None:
        """
        Scrollable form area that dynamically stretches to fill the entire window width.
        """
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.grid(row=1, column=0, sticky="nsew")
        
        # ---> THE FIX: Give all horizontal stretching power to column 1 <---
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        center = ctk.CTkFrame(outer, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew")
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=1)

        self._fields_frame = ctk.CTkScrollableFrame(
            center,
            fg_color="transparent",
            # We no longer need a hardcoded width=1000 because sticky="nsew" + weight=1
            # forces it to calculate the window width automatically!
        )
        self._fields_frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=(12, 0))
        self._fields_frame.grid_columnconfigure(0, weight=1)
        
    def _build_buttons(self) -> None:
        """Save and Cancel buttons pinned to the bottom, centred."""
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.grid(row=2, column=0, sticky="ew", padx=24, pady=14)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(
            outer,
            text="إلغاء  /  Cancel",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=40,
            width=160,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color="gray60",
            hover_color="gray50",
            command=self.close,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            outer,
            text="حفظ  /  Save",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=40,
            width=160,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._handle_save,
        ).grid(row=0, column=2, padx=(8, 0))

    # =========================================================================
    # Field builder helpers — subclasses call these inside _build_fields()
    # =========================================================================

    def _add_entry(
        self, label_ar: str, label_en: str, placeholder: str = "", 
        row: int = None, col: int = 0, colspan: int = 1,
        justify: str = "right", parent=None
    ) -> ctk.CTkEntry:
        """Add a labeled text entry field to the panel."""
        target = parent if parent is not None else self._fields_frame
        if row is None:
            row = self._field_row
            self._field_row += 2

        ctk.CTkLabel(
            target,
            text=f"{label_ar}  /  {label_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=row, column=col, columnspan=colspan, sticky="e", pady=(8, 2), padx=10)

        entry = ctk.CTkEntry(
            target,
            placeholder_text=placeholder,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            justify=justify,
        )
        entry.grid(row=row+1, column=col, columnspan=colspan, sticky="ew", pady=(0, 2), padx=10)

        try:
            entry._entry.configure(justify=justify)
        except Exception:
            pass

        return entry

    def _add_dropdown(
        self, label_ar: str, label_en: str, values: list[str], 
        row: int = None, col: int = 0, colspan: int = 1, parent=None
    ) -> ctk.CTkOptionMenu:
        """Add a labeled dropdown to the panel."""
        target = parent if parent is not None else self._fields_frame
        if row is None:
            row = self._field_row
            self._field_row += 2

        ctk.CTkLabel(
            target,
            text=f"{label_ar}  /  {label_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=row, column=col, columnspan=colspan, sticky="e", pady=(8, 2), padx=10)

        dropdown = ctk.CTkOptionMenu(
            target,
            values=values,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
            anchor="e",
        )
        dropdown.grid(row=row+1, column=col, columnspan=colspan, sticky="ew", pady=(0, 2), padx=10)

        if values:
            dropdown.set(values)

        return dropdown

    def _add_combobox(
        self, label_ar: str, label_en: str, values: list[str], 
        row: int = None, col: int = 0, colspan: int = 1, parent=None
    ) -> ctk.CTkComboBox:
        """Add a labeled combobox (editable dropdown) to the panel."""
        target = parent if parent is not None else self._fields_frame
        if row is None:
            row = self._field_row
            self._field_row += 2

        ctk.CTkLabel(
            target,
            text=f"{label_ar}  /  {label_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=row, column=col, columnspan=colspan, sticky="e", pady=(8, 2), padx=10)

        combo = ctk.CTkComboBox(
            target,
            values=values,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=36,
        )
        combo.grid(row=row+1, column=col, columnspan=colspan, sticky="ew", pady=(0, 2), padx=10)
        
        if values:
            combo.set(values[0])

        return combo

    def _add_section_label(self, text_ar: str, text_en: str, row: int = None, col: int = 0, colspan: int = 1, parent=None) -> None:
        """Add a visual section divider with a bilingual subheading."""
        target = parent if parent is not None else self._fields_frame
        if row is None:
            row = self._field_row
            self._field_row += 2

        ctk.CTkFrame(
            target,
            height=1,
            fg_color=AppColors.DIVIDER,
        ).grid(row=row, column=col, columnspan=colspan, sticky="ew", pady=(18, 0), padx=10)

        ctk.CTkLabel(
            target,
            text=f"{text_ar}  —  {text_en}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=row+1, column=col, columnspan=colspan, sticky="e", pady=(4, 4), padx=10)

    # =========================================================================
    # Convenience write helpers
    # =========================================================================

    def _set_entry(self, entry: ctk.CTkEntry, value: str) -> None:
        """Clear an entry field and set a new value."""
        entry.delete(0, "end")
        if value:
            entry.insert(0, str(value))

    def _set_dropdown(self, dropdown: ctk.CTkOptionMenu, value: str) -> None:
        """Set the selected value of a dropdown if the value exists."""
        try:
            dropdown.set(value)
        except Exception:
            pass

    def _clear_all_entries(self) -> None:
        """Clear every CTkEntry in the fields frame."""
        for widget in self._fields_frame.winfo_children():
            if isinstance(widget, ctk.CTkEntry):
                widget.delete(0, "end")

    # =========================================================================
    # Open / Close (full-page mode)
    # =========================================================================

    def open_add(self) -> None:
        """Show the panel in Add mode."""
        self._existing = None
        self._clear_all_entries()
        self._clear_error()
        self._title_label.configure(
            text=f"{self._title_ar_add}  —  {self._title_en_add}"
        )
        self._show()

    def open_edit(self, data: dict) -> None:
        """Show the panel in Edit mode, pre-filled with data."""
        self._existing = data
        self._clear_error()
        self._title_label.configure(
            text=f"{self._title_ar_edit}  —  {self._title_en_edit}"
        )
        self._populate(data)
        self._show()

    def close(self) -> None:
        """Hide the form and restore all sibling widgets."""
        self.grid_remove()
        for sibling in self._hidden_siblings:
            sibling.grid()
        self._hidden_siblings.clear()

    def _show(self) -> None:
        """
        Hide every other widget in the parent frame, then grid self
        so it fills the entire parent area.
        """
        self._hidden_siblings = []
        for child in self._parent.winfo_children():
            if child is self:
                continue
            if child.winfo_ismapped():
                child.grid_remove()
                self._hidden_siblings.append(child)

        # Fill entire parent
        self._parent.grid_columnconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky="nsew", rowspan=20)

    # =========================================================================
    # Save flow
    # =========================================================================

    def _handle_save(self) -> None:
        """Validate → save → callback → close."""
        self._clear_error()

        error = self._validate()
        if error:
            self._show_error(error)
            return

        try:
            self._on_save(self._existing)
            self._on_save_callback()
            self.close()
        except Exception as e:
            self._show_error(f"خطأ في الحفظ  —  Save error:\n{e}")

    def _show_error(self, message: str) -> None:
        """Display an error message inline at the bottom of the fields area."""
        self._clear_error()
        self._error_label = ctk.CTkLabel(
            self._fields_frame,
            text=f"⚠️  {message}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            text_color=AppColors.COLOR_ERROR,
            wraplength=500,
            justify="right",
            anchor="e",
        )
        # We use row 1000 to guarantee it always drops to the very bottom of the grid
        self._error_label.grid(row=1000, column=0, columnspan=3, sticky="e", pady=(15, 0), padx=10)

    def _clear_error(self) -> None:
        """Remove the inline error label if one exists."""
        if self._error_label:
            self._error_label.destroy()
            self._error_label = None

    # =========================================================================
    # Abstract methods — subclasses MUST implement all four
    # =========================================================================

    @abstractmethod
    def _build_fields(self) -> None:
        """Build the form fields using self._add_entry() / self._add_dropdown()."""

    @abstractmethod
    def _populate(self, data: dict) -> None:
        """Pre-fill all fields with values from data (used in Edit mode)."""

    @abstractmethod
    def _validate(self) -> str | None:
        """Validate all fields. Return None if valid, or an error string."""

    @abstractmethod
    def _on_save(self, existing: dict | None) -> None:
        """Write form data to the database. Do NOT call self.close() here."""
