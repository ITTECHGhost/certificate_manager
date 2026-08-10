# =============================================================================
# ui/pagination_bar.py — Reusable Pagination Controls
# =============================================================================
#
# PURPOSE:
#   A self-contained row of pagination controls that any screen can embed.
#   Shows: [page-size picker] ... [◄ Prev]  Page X of Y  [Next ►]
#
# HOW TO USE:
#   bar = PaginationBar(parent, on_change=self._on_page_change)
#   bar.grid(row=3, column=0, sticky="ew")
#
#   def _on_page_change(page: int, page_size: int) -> None:
#       data = my_query(limit=page_size, offset=(page - 1) * page_size)
#       self._render_list(data)
#
#   # After loading data call:
#   bar.set_total(total_records)
#
# =============================================================================

import customtkinter as ctk
from config import AppFonts, AppColors, AppSizes

PAGE_SIZE_OPTIONS = ["10", "25", "50", "100"]


class PaginationBar(ctk.CTkFrame):
    """
    Pagination controls: page-size chooser + prev/next buttons + page indicator.
    """

    def __init__(self, parent, on_change) -> None:
        """
        Args:
            parent:    Parent widget.
            on_change: Callable[[page: int, page_size: int], None]
                       Called whenever the user changes page or page size.
        """
        super().__init__(parent, fg_color="transparent")
        self._on_change  = on_change
        self._page       = 1
        self._page_size  = 25
        self._total      = 0
        self._build()

    # ─────────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Page-size picker (left)
        size_frame = ctk.CTkFrame(self, fg_color="transparent")
        size_frame.grid(row=0, column=0, sticky="w", padx=(0, 8))

        ctk.CTkLabel(
            size_frame,
            text="عرض  /  Show:",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
        ).grid(row=0, column=0, padx=(0, 4))

        self._size_var = ctk.StringVar(value=str(self._page_size))
        ctk.CTkOptionMenu(
            size_frame,
            variable=self._size_var,
            values=PAGE_SIZE_OPTIONS,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=70,
            height=30,
            command=self._on_size_change,
        ).grid(row=0, column=1)

        # Nav controls (centre)
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=1)

        self._prev_btn = ctk.CTkButton(
            nav,
            text="◄  السابق",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=90,
            height=30,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._go_prev,
        )
        self._prev_btn.grid(row=0, column=0, padx=(0, 8))

        self._label = ctk.CTkLabel(
            nav,
            text="—",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=120,
        )
        self._label.grid(row=0, column=1, padx=4)

        self._next_btn = ctk.CTkButton(
            nav,
            text="التالي  ►",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=90,
            height=30,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            command=self._go_next,
        )
        self._next_btn.grid(row=0, column=2, padx=(8, 0))

        self._refresh_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_total(self, total: int) -> None:
        """
        Update the total record count and refresh the UI.
        Call this after loading/reloading data.
        """
        self._total = max(0, total)
        # Clamp page to valid range
        max_page = max(1, self._total_pages())
        if self._page > max_page:
            self._page = max_page
        self._refresh_ui()

    @property
    def page(self) -> int:
        return self._page

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def offset(self) -> int:
        return (self._page - 1) * self._page_size

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _total_pages(self) -> int:
        if self._total == 0:
            return 1
        return (self._total + self._page_size - 1) // self._page_size

    def _refresh_ui(self) -> None:
        total_pages = self._total_pages()
        self._label.configure(
            text=f"صفحة {self._page} من {total_pages}  /  Page {self._page} of {total_pages}"
        )
        self._prev_btn.configure(state="normal" if self._page > 1 else "disabled")
        self._next_btn.configure(state="normal" if self._page < total_pages else "disabled")

    def _go_prev(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._refresh_ui()
            self._on_change(self._page, self._page_size)

    def _go_next(self) -> None:
        if self._page < self._total_pages():
            self._page += 1
            self._refresh_ui()
            self._on_change(self._page, self._page_size)

    def _on_size_change(self, value: str) -> None:
        self._page_size = int(value)
        self._page = 1          # reset to first page
        self._refresh_ui()
        self._on_change(self._page, self._page_size)
