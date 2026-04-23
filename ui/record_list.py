# =============================================================================
# ui/record_list.py — Reusable Scrollable Record List Widget
# =============================================================================
#
# CHANGES:
#   - Optional on_extra callback + extra_label / extra_color for a third
#     action button per row (used by GraduationOrdersScreen for "View Students").
#
# =============================================================================

import customtkinter as ctk
from config import AppFonts, AppColors, AppSizes


class RecordList(ctk.CTkFrame):
    """
    A scrollable table widget with a fixed header row and one data row
    per record. Each row shows configurable columns plus Edit / Delete buttons
    and optionally a third action button.
    """

    ACTION_BTN_WIDTH = 70

    def __init__(
        self,
        parent,
        columns: list[tuple[str, int]],
        on_edit,
        on_delete,
        on_extra=None,              # Optional extra action callback
        extra_label: str = "عرض\nView",
        extra_color: str = AppColors.ACCENT_GREEN,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._columns    = columns
        self._on_edit    = on_edit
        self._on_delete  = on_delete
        self._on_extra   = on_extra
        self._extra_label = extra_label
        self._extra_color = extra_color
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # -------------------------------------------------------------------------
    # Build
    # -------------------------------------------------------------------------

    def _build(self) -> None:
        self._build_header()
        self._build_body()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self,
            fg_color=("gray82", "gray25"),
            corner_radius=6,
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))

        for col_idx, (title, width) in enumerate(self._columns):
            ctk.CTkLabel(
                header,
                text=title,
                font=ctk.CTkFont(
                    family=AppFonts.FAMILY,
                    size=AppFonts.SIZE_SMALL,
                    weight="bold",
                ),
                width=width,
                anchor="center",
            ).grid(row=0, column=col_idx, padx=4, pady=8)

        # Actions header — wider if extra button present
        n_btns = 3 if self._on_extra else 2
        ctk.CTkLabel(
            header,
            text="إجراءات  /  Actions",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SMALL,
                weight="bold",
            ),
            width=self.ACTION_BTN_WIDTH * n_btns + (n_btns - 1) * 4,
            anchor="center",
        ).grid(row=0, column=len(self._columns), padx=4, pady=8)

    def _build_body(self) -> None:
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load(
        self,
        rows: list[dict],
        cell_extractor,
    ) -> None:
        self._clear()

        if not rows:
            self._show_empty_message()
            return

        for row_idx, row_data in enumerate(rows):
            self._add_row(row_idx, row_data, cell_extractor(row_data))

    def _clear(self) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()

    def _show_empty_message(self) -> None:
        ctk.CTkLabel(
            self._scroll,
            text="لا توجد سجلات  —  No records found",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            text_color=AppColors.TEXT_MUTED,
        ).grid(row=0, column=0, pady=30)

    def _add_row(
        self,
        row_idx: int,
        row_data: dict,
        cell_values: list[str],
    ) -> None:
        bg = ("gray96", "gray20") if row_idx % 2 == 0 else ("white", "gray23")

        row_frame = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=4)
        row_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)

        for col_idx, (text, width) in enumerate(
            zip(cell_values, [w for _, w in self._columns])
        ):
            ctk.CTkLabel(
                row_frame,
                text=text,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                width=width,
                anchor="center",
                wraplength=width - 10,
            ).grid(row=0, column=col_idx, padx=4, pady=6)

        btn_col = len(self._columns)

        # Extra button (optional — e.g. "View Students")
        if self._on_extra:
            ctk.CTkButton(
                row_frame,
                text=self._extra_label,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
                width=self.ACTION_BTN_WIDTH,
                height=34,
                corner_radius=AppSizes.CORNER_RADIUS_BTN,
                fg_color=self._extra_color,
                hover_color="#2E7D32",
                command=lambda d=row_data: self._on_extra(d),
            ).grid(row=0, column=btn_col, padx=(4, 2), pady=4)
            btn_col += 1

        # Edit button
        ctk.CTkButton(
            row_frame,
            text="تعديل\nEdit",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=self.ACTION_BTN_WIDTH,
            height=34,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color=AppColors.COLOR_INFO,
            hover_color="#1565C0",
            command=lambda d=row_data: self._on_edit(d),
        ).grid(row=0, column=btn_col, padx=(4, 2), pady=4)

        # Delete button
        ctk.CTkButton(
            row_frame,
            text="حذف\nDelete",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=self.ACTION_BTN_WIDTH,
            height=34,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color=AppColors.COLOR_ERROR,
            hover_color="#B71C1C",
            command=lambda d=row_data: self._on_delete(d),
        ).grid(row=0, column=btn_col + 1, padx=(2, 4), pady=4)
