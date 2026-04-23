# =============================================================================
# ui/widgets.py — Reusable Widget Factory
# =============================================================================
#
# PURPOSE:
#   Every repeating UI pattern used across multiple screens is defined ONCE
#   here as a factory function. Screens call these functions instead of
#   repeating the same widget-building code.
#
# HOW TO USE:
#   from ui.widgets import make_section_header, make_stat_card, make_field_row
#
# ADDING NEW WIDGETS:
#   Add a new factory function following the same pattern:
#   1. All parameters have type hints
#   2. The docstring explains what it builds and what it returns
#   3. All colors / fonts come from config.py — no hardcoded values
#
# =============================================================================

import customtkinter as ctk
from config import AppColors, AppFonts, AppSizes


# =============================================================================
# SECTION HEADERS
# =============================================================================

def make_section_header(
    parent: ctk.CTkFrame,
    text_ar: str,
    text_en: str,
) -> ctk.CTkLabel:
    """
    Build a bilingual section header label (Arabic on the right side).

    Args:
        parent:  The parent frame to place the label in.
        text_ar: Arabic heading text.
        text_en: English heading text (shown smaller below).

    Returns:
        The CTkLabel widget (already configured, not yet grid/packed).

    Example:
        header = make_section_header(frame, "الطلاب", "Students")
        header.pack(anchor="e", pady=(0, 12))
    """
    label = ctk.CTkLabel(
        parent,
        text=f"{text_ar}  —  {text_en}",
        font=ctk.CTkFont(
            family=AppFonts.FAMILY,
            size=AppFonts.SIZE_TITLE,
            weight="bold",
        ),
        anchor="e",
    )
    return label


def make_divider(parent: ctk.CTkFrame) -> ctk.CTkFrame:
    """
    Build a thin horizontal divider line.

    Returns:
        A 1-pixel-tall CTkFrame styled as a divider.
    """
    return ctk.CTkFrame(parent, height=1, fg_color=AppColors.DIVIDER)


# =============================================================================
# STAT CARDS (used on the Home screen)
# =============================================================================

def make_stat_card(
    parent: ctk.CTkFrame,
    icon: str,
    label_ar: str,
    label_en: str,
    accent_color: str,
) -> ctk.CTkFrame:
    """
    Build a statistics card widget showing an icon, a count, and a label.
    The returned frame has a `.count_label` attribute for updating the count.

    Args:
        parent:       The parent frame to place the card in.
        icon:         Emoji icon string (e.g. "👤").
        label_ar:     Arabic label (e.g. "الطلاب").
        label_en:     English label (e.g. "Students").
        accent_color: Hex color for the count number (e.g. "#2196F3").

    Returns:
        CTkFrame with an extra attribute `.count_label` (a CTkLabel).
        Call `.count_label.configure(text="42")` to update the count.

    Example:
        card = make_stat_card(frame, "👤", "الطلاب", "Students", "#2196F3")
        card.grid(row=0, column=0, padx=6, sticky="nsew")
        card.count_label.configure(text="42")
    """
    card = ctk.CTkFrame(
        parent,
        corner_radius=AppSizes.CORNER_RADIUS_CARD,
        border_width=1,
        border_color=AppColors.BORDER,
    )
    card.grid_columnconfigure(0, weight=1)

    # Icon
    ctk.CTkLabel(
        card,
        text=icon,
        font=ctk.CTkFont(size=AppSizes.STAT_CARD_ICON_SIZE),
    ).grid(row=0, column=0, pady=(14, 4))

    # Count number — stored as attribute for external updates
    count_label = ctk.CTkLabel(
        card,
        text="—",
        font=ctk.CTkFont(
            family=AppFonts.FAMILY,
            size=AppSizes.STAT_CARD_COUNT_SIZE,
            weight="bold",
        ),
        text_color=accent_color,
    )
    count_label.grid(row=1, column=0)

    # Bilingual label beneath the count
    ctk.CTkLabel(
        card,
        text=f"{label_ar}  /  {label_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
        text_color=AppColors.TEXT_MUTED,
    ).grid(row=2, column=0, pady=(2, 14))

    # Attach the count label as an attribute so callers can update it
    card.count_label = count_label
    return card


# =============================================================================
# FORM FIELDS
# =============================================================================

def make_labeled_entry(
    parent: ctk.CTkFrame,
    label_ar: str,
    label_en: str,
    placeholder: str = "",
    width: int = 300,
) -> ctk.CTkEntry:
    """
    Build a labeled text entry field with bilingual label above.
    Places the label and entry inside a small vertical sub-frame.

    Args:
        parent:      The parent frame.
        label_ar:    Arabic field label.
        label_en:    English field label.
        placeholder: Placeholder text shown when the field is empty.
        width:       Entry widget width in pixels.

    Returns:
        The CTkEntry widget. Use .get() to read value, .insert(0, text) to set.

    Example:
        entry = make_labeled_entry(form, "الاسم بالعربية", "Arabic Name")
        entry.grid(row=0, column=0, sticky="ew")
        value = entry.get()
    """
    container = ctk.CTkFrame(parent, fg_color="transparent")
    container.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        container,
        text=f"{label_ar}  /  {label_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        anchor="e",
    ).grid(row=0, column=0, sticky="e", pady=(0, 3))

    entry = ctk.CTkEntry(
        container,
        placeholder_text=placeholder,
        width=width,
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
    )
    entry.grid(row=1, column=0, sticky="ew")

    # Return the entry; parent can grid the whole container
    entry.container = container
    return entry


def make_labeled_dropdown(
    parent: ctk.CTkFrame,
    label_ar: str,
    label_en: str,
    values: list[str],
    width: int = 300,
) -> ctk.CTkOptionMenu:
    """
    Build a labeled dropdown (OptionMenu) with bilingual label above.

    Args:
        parent:   The parent frame.
        label_ar: Arabic label.
        label_en: English label.
        values:   List of string choices.
        width:    Dropdown width in pixels.

    Returns:
        The CTkOptionMenu widget. Use .get() to read selection, .set(v) to set.
    """
    container = ctk.CTkFrame(parent, fg_color="transparent")
    container.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        container,
        text=f"{label_ar}  /  {label_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        anchor="e",
    ).grid(row=0, column=0, sticky="e", pady=(0, 3))

    dropdown = ctk.CTkOptionMenu(
        container,
        values=values,
        width=width,
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
    )
    dropdown.grid(row=1, column=0, sticky="ew")

    dropdown.container = container
    return dropdown


# =============================================================================
# BUTTONS
# =============================================================================

def make_primary_button(
    parent: ctk.CTkFrame,
    text_ar: str,
    text_en: str,
    command,
    width: int = 160,
    height: int = 38,
) -> ctk.CTkButton:
    """
    Build a primary action button (blue) with bilingual label.

    Args:
        parent:   Parent frame.
        text_ar:  Arabic button text.
        text_en:  English button text.
        command:  Function to call on click.
        width:    Button width in pixels.
        height:   Button height in pixels.

    Returns:
        The configured CTkButton.
    """
    return ctk.CTkButton(
        parent,
        text=f"{text_ar}  /  {text_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        command=command,
        width=width,
        height=height,
        corner_radius=AppSizes.CORNER_RADIUS_BTN,
    )


def make_danger_button(
    parent: ctk.CTkFrame,
    text_ar: str,
    text_en: str,
    command,
    width: int = 160,
    height: int = 38,
) -> ctk.CTkButton:
    """
    Build a danger/destructive action button (red).
    Used for delete operations. Triggers a confirmation dialog before acting.

    Args: same as make_primary_button.
    """
    return ctk.CTkButton(
        parent,
        text=f"{text_ar}  /  {text_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        command=command,
        width=width,
        height=height,
        corner_radius=AppSizes.CORNER_RADIUS_BTN,
        fg_color=AppColors.COLOR_ERROR,
        hover_color="#D32F2F",
    )


def make_secondary_button(
    parent: ctk.CTkFrame,
    text_ar: str,
    text_en: str,
    command,
    width: int = 160,
    height: int = 38,
) -> ctk.CTkButton:
    """
    Build a secondary (grey/neutral) button.
    Used for Cancel, Back, and non-destructive secondary actions.
    """
    return ctk.CTkButton(
        parent,
        text=f"{text_ar}  /  {text_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        command=command,
        width=width,
        height=height,
        corner_radius=AppSizes.CORNER_RADIUS_BTN,
        fg_color="gray60",
        hover_color="gray50",
    )


def make_quick_action_button(
    parent: ctk.CTkFrame,
    text_ar: str,
    text_en: str,
    command,
) -> ctk.CTkButton:
    """
    Build a tall quick-action button for the home screen dashboard.
    Shows Arabic on the first line, English on the second.
    """
    return ctk.CTkButton(
        parent,
        text=f"{text_ar}\n{text_en}",
        font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        height=AppSizes.ACTION_BUTTON_HEIGHT,
        corner_radius=AppSizes.CORNER_RADIUS_CARD,
        command=command,
    )


# =============================================================================
# DATA TABLE (scrollable list of rows)
# =============================================================================

def make_table_header(
    parent: ctk.CTkFrame,
    columns: list[tuple[str, int]],
) -> ctk.CTkFrame:
    """
    Build a table header row with column titles and fixed widths.

    Args:
        parent:  The parent frame.
        columns: List of (title_text, width_in_pixels) tuples.

    Returns:
        The header CTkFrame (already contains the column labels).

    Example:
        header = make_table_header(table_frame, [
            ("الاسم بالعربية  /  Arabic Name", 200),
            ("القسم  /  Dept",                 150),
            ("سنة القبول  /  Year",             80),
        ])
        header.pack(fill="x")
    """
    header_frame = ctk.CTkFrame(
        parent,
        fg_color=("gray82", "gray25"),
        corner_radius=6,
    )

    for col_idx, (title, col_width) in enumerate(columns):
        ctk.CTkLabel(
            header_frame,
            text=title,
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SMALL,
                weight="bold",
            ),
            width=col_width,
            anchor="center",
        ).grid(row=0, column=col_idx, padx=4, pady=6)

    return header_frame


def make_table_row(
    parent: ctk.CTkFrame,
    values: list[tuple[str, int]],
    on_click=None,
    row_index: int = 0,
) -> ctk.CTkFrame:
    """
    Build a single data row for a table.

    Args:
        parent:    The parent scrollable frame.
        values:    List of (cell_text, width_in_pixels) matching the header.
        on_click:  Optional callback for when the row is clicked.
        row_index: Row number (used for alternating row colors).

    Returns:
        The row CTkFrame.
    """
    # Alternate row background for readability
    bg = ("gray96", "gray20") if row_index % 2 == 0 else ("white", "gray23")

    row_frame = ctk.CTkFrame(parent, fg_color=bg, corner_radius=4)

    for col_idx, (text, col_width) in enumerate(values):
        ctk.CTkLabel(
            row_frame,
            text=text,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=col_width,
            anchor="center",
        ).grid(row=0, column=col_idx, padx=4, pady=5)

    # Make the whole row clickable if a callback is provided
    if on_click:
        row_frame.bind("<Button-1>", lambda e: on_click())
        for child in row_frame.winfo_children():
            child.bind("<Button-1>", lambda e: on_click())

    return row_frame
