# =============================================================================
# screens/history_screen.py — Admin Change History (Audit Log)
# =============================================================================
#
# PURPOSE:
#   Displays the audit_log table so administrators can monitor all
#   INSERT / UPDATE / DELETE / ERROR events across the application.
#
# FEATURES:
#   - Filter by table name and action type
#   - Paginated (25/50/100 rows per page)
#   - Error rows highlighted in red
#
# =============================================================================

import customtkinter as ctk

from config import AppFonts, AppColors, AppSizes
from data.queries import get_audit_log, count_audit_log
from ui.base_screen import BaseScreen
from ui.pagination_bar import PaginationBar
from ui.widgets import make_section_header


ACTION_COLORS = {
    "INSERT": AppColors.ACCENT_GREEN,
    "UPDATE": AppColors.ACCENT_BLUE,
    "DELETE": AppColors.COLOR_ERROR,
    "ERROR":  AppColors.COLOR_ERROR,
}

TABLE_LABELS = {
    "": "كل الجداول  —  All Tables",
    "personal":           "الكوادر  /  Personal",
    "courses":            "المواد  /  Courses",
    "students":           "الطلاب  /  Students",
    "departments":        "الأقسام  /  Departments",
    "graduation_orders":  "أوامر التخرج  /  Orders",
}

ACTION_LABELS = {
    "": "كل الأحداث  —  All Actions",
    "INSERT": "إضافة  /  INSERT",
    "UPDATE": "تعديل  /  UPDATE",
    "DELETE": "حذف  /  DELETE",
    "ERROR":  "خطأ  /  ERROR",
}


class HistoryScreen(BaseScreen):
    """Admin audit-log viewer with filter + pagination."""

    COLUMNS = [
        ("#",                         30),
        ("الجدول  /  Table",         130),
        ("الحدث  /  Action",          80),
        ("الوصف  /  Summary",        280),
        ("التاريخ  /  Date",         150),
    ]

    def __init__(self, parent, switch_callback) -> None:
        self._table_filter  = ""
        self._action_filter = ""
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header row
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(1, weight=1)

        make_section_header(top, "سجل التغييرات", "Change History").grid(
            row=0, column=1, sticky="e"
        )

        # Filter row
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        filter_row.grid_columnconfigure(2, weight=1)

        # Table filter
        self._table_var = ctk.StringVar(value=TABLE_LABELS[""])
        ctk.CTkOptionMenu(
            filter_row,
            variable=self._table_var,
            values=list(TABLE_LABELS.values()),
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=220,
            height=32,
            command=self._on_filter_change,
        ).grid(row=0, column=0, padx=(0, 8))

        # Action filter
        self._action_var = ctk.StringVar(value=ACTION_LABELS[""])
        ctk.CTkOptionMenu(
            filter_row,
            variable=self._action_var,
            values=list(ACTION_LABELS.values()),
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=160,
            height=32,
            command=self._on_filter_change,
        ).grid(row=0, column=1, padx=(0, 8))

        # Spacer
        ctk.CTkLabel(filter_row, text="").grid(row=0, column=2, sticky="ew")

        # Refresh button
        ctk.CTkButton(
            filter_row,
            text="🔄 تحديث  /  Refresh",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=130,
            height=32,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self.refresh,
        ).grid(row=0, column=3)

        # Log table (scrollable)
        self._build_table_header()
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=2, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        # Pagination
        self._pager = PaginationBar(self, on_change=self._on_page_change)
        self._pager.grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def _build_table_header(self) -> None:
        header = ctk.CTkFrame(
            self, fg_color=("gray82", "gray25"), corner_radius=6
        )
        header.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        header.grid_forget()           # replaced by filter_row; rebuild after
        # Actually build it in row 1 properly below
        header2 = ctk.CTkFrame(
            self, fg_color=("gray82", "gray25"), corner_radius=6
        )
        # We'll just build it inline in refresh — skip a separate frame.
        header.destroy()
        header2.destroy()

    def refresh(self) -> None:
        self._table_filter  = self._resolve_table()
        self._action_filter = self._resolve_action()
        total = count_audit_log(self._table_filter, self._action_filter)
        self._pager.set_total(total)
        self._load_page()

    def _on_filter_change(self, _=None) -> None:
        self._pager._page = 1
        self.refresh()

    def _on_page_change(self, page: int, page_size: int) -> None:
        self._load_page()

    def _load_page(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

        rows = get_audit_log(
            table_filter  = self._table_filter,
            action_filter = self._action_filter,
            limit         = self._pager.page_size,
            offset        = self._pager.offset,
        )

        if not rows:
            ctk.CTkLabel(
                self._scroll,
                text="لا توجد سجلات  —  No records found",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
                text_color=AppColors.TEXT_MUTED,
            ).grid(row=0, column=0, pady=30)
            return

        # Header row
        hdr = ctk.CTkFrame(
            self._scroll, fg_color=("gray82", "gray25"), corner_radius=4
        )
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        widths = [w for _, w in self.COLUMNS]
        for ci, (title, width) in enumerate(self.COLUMNS):
            ctk.CTkLabel(
                hdr, text=title,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
                width=width, anchor="center",
            ).grid(row=0, column=ci, padx=4, pady=6)

        for ri, row in enumerate(rows):
            bg = ("gray96", "gray20") if ri % 2 == 0 else ("white", "gray23")
            is_error = row["action"] in ("ERROR", "DELETE")
            if is_error:
                bg = ("#FFEBEE", "#3E1111")

            rf = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=4)
            rf.grid(row=ri + 1, column=0, sticky="ew", pady=1)

            action_color = ACTION_COLORS.get(row["action"], AppColors.TEXT_MUTED)

            cells = [
                str(self._pager.offset + ri + 1),
                row["table_name"],
                row["action"],
                (row.get("summary") or row.get("error_info") or "—")[:80],
                row["created_at"],
            ]
            for ci, (text, width) in enumerate(zip(cells, widths)):
                kwargs = {}
                if ci == 2:   # Action column: color-coded
                    kwargs["text_color"] = action_color
                ctk.CTkLabel(
                    rf, text=text,
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                    width=width, anchor="center",
                    wraplength=width - 10,
                    **kwargs,
                ).grid(row=0, column=ci, padx=4, pady=5)

            # Error details button if there is error info
            if row.get("error_info"):
                ctk.CTkButton(
                    rf,
                    text="تفاصيل\nDetails",
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                    width=60, height=28,
                    corner_radius=4,
                    fg_color=AppColors.COLOR_ERROR,
                    hover_color="#B71C1C",
                    command=lambda ei=row["error_info"]: self.show_error(ei),
                ).grid(row=0, column=len(cells), padx=4, pady=4)

    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_table(self) -> str:
        sel = self._table_var.get()
        for k, v in TABLE_LABELS.items():
            if v == sel:
                return k
        return ""

    def _resolve_action(self) -> str:
        sel = self._action_var.get()
        for k, v in ACTION_LABELS.items():
            if v == sel:
                return k
        return ""
