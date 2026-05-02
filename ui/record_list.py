# =============================================================================
# ui/record_list.py — Reusable Scrollable Record List Widget
# =============================================================================

import customtkinter as ctk
from config import AppFonts, AppColors, AppSizes

class RecordList(ctk.CTkFrame):
    """
    A scrollable table widget with a fixed header row and one data row
    per record. Optimized for both LTR and RTL layouts.
    """

    ACTION_BTN_WIDTH = 75
    ROW_HEIGHT = 45

    def __init__(
        self,
        parent,
        columns: list[tuple[str, int]],
        on_edit,
        on_delete,
        on_extra=None,
        extra_label: str = "عرض\nView",
        extra_color: str = AppColors.ACCENT_GREEN,
        on_cell_click=None,
        is_rtl: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._columns = columns
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_extra = on_extra
        self._extra_label = extra_label
        self._extra_color = extra_color
        self._on_cell_click = on_cell_click
        self._is_rtl = is_rtl
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._n_btns = (3 if on_extra else 2)
        self._total_cols = len(columns) + self._n_btns
        
        self._build()

    def _build(self) -> None:
        self._header_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"), corner_radius=8)
        self._header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self._setup_grid(self._header_frame)
        self._build_header()
        
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

    def _setup_grid(self, frame: ctk.CTkFrame) -> None:
        """Setup column weights and minimum sizes for a row or header."""
        # Action columns (no weight)
        actions_start = 0 if self._is_rtl else len(self._columns)
        for i in range(self._n_btns):
            frame.grid_columnconfigure(actions_start + i, minsize=self.ACTION_BTN_WIDTH + 10)
        
        # Data columns
        for i, (_, width) in enumerate(self._columns):
            col_idx = (self._total_cols - 1 - i) if self._is_rtl else i
            # Give the first column (Name) more weight if possible, or just distribute
            weight = 1 if i == 0 else 0
            frame.grid_columnconfigure(col_idx, minsize=width, weight=weight)

    def _build_header(self) -> None:
        # Actions label
        actions_col = 0 if self._is_rtl else len(self._columns)
        ctk.CTkLabel(
            self._header_frame,
            text="إجراءات / Actions",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
        ).grid(row=0, column=actions_col, columnspan=self._n_btns, pady=10, sticky="nsew")

        # Data labels
        for i, (title, _) in enumerate(self._columns):
            col_idx = (self._total_cols - 1 - i) if self._is_rtl else i
            ctk.CTkLabel(
                self._header_frame,
                text=title,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            ).grid(row=0, column=col_idx, pady=10, sticky="nsew")

    def load(self, rows: list[dict], cell_extractor) -> None:
        self._clear()
        if not rows:
            self._show_empty_message()
            return

        for idx, row_data in enumerate(rows):
            self._add_row(idx, row_data, cell_extractor(row_data))

    def _clear(self) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()

    def _show_empty_message(self) -> None:
        ctk.CTkLabel(
            self._scroll,
            text="لا توجد سجلات — No records found",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            text_color=AppColors.TEXT_MUTED,
        ).grid(row=0, column=0, pady=40)

    def _add_row(self, row_idx: int, row_data: dict, cell_values: list[str]) -> None:
        bg = ("gray98", "gray25") if row_idx % 2 == 0 else ("gray92", "gray22")
        
        row_frame = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=6, height=self.ROW_HEIGHT)
        row_frame.grid(row=row_idx, column=0, sticky="ew", pady=2, padx=2)
        row_frame.grid_propagate(False) # Force height
        self._setup_grid(row_frame)
        row_frame.grid_rowconfigure(0, weight=1)

        # Data Cells
        for i, text in enumerate(cell_values):
            col_idx = (self._total_cols - 1 - i) if self._is_rtl else i
            lbl = ctk.CTkLabel(
                row_frame,
                text=text,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                anchor="center",
                cursor="hand2" if self._on_cell_click else "arrow"
            )
            lbl.grid(row=0, column=col_idx, padx=5, sticky="nsew")
            if self._on_cell_click:
                lbl.bind("<Button-1>", lambda e, d=row_data, idx=i: self._on_cell_click(d, idx))

        # Action Buttons
        btn_start = 0 if self._is_rtl else len(self._columns)
        curr_col = btn_start
        
        if self._on_extra:
            self._make_btn(row_frame, self._extra_label, self._extra_color, 
                          lambda d=row_data: self._on_extra(d)).grid(row=0, column=curr_col, padx=2)
            curr_col += 1
            
        self._make_btn(row_frame, "تعديل\nEdit", AppColors.COLOR_INFO, 
                      lambda d=row_data: self._on_edit(d)).grid(row=0, column=curr_col, padx=2)
        curr_col += 1
        
        self._make_btn(row_frame, "حذف\nDelete", AppColors.COLOR_ERROR, 
                      lambda d=row_data: self._on_delete(d)).grid(row=0, column=curr_col, padx=2)

    def _make_btn(self, parent, text, color, command):
        return ctk.CTkButton(
            parent,
            text=text,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=self.ACTION_BTN_WIDTH,
            height=32,
            fg_color=color,
            hover_color=("#333", "#444"),
            command=command,
            corner_radius=6
        )
