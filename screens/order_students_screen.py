# =============================================================================
# screens/order_students_screen.py — Link/Unlink Students to a Graduation Order
# =============================================================================
#
# OPENED FROM: GraduationOrdersScreen → "View Students" button.
# NAVIGATION:  ← Back arrow returns to graduation orders list.
#
# LAYOUT:
#   Top: order info banner + back arrow
#   Left panel  (50%): linked students list + Unlink button per row
#   Right panel (50%): search/filter panel → search results + Link button
#
# =============================================================================

import customtkinter as ctk

from config import AppFonts, AppColors, AppSizes
from data.queries import (
    get_students_for_order, search_students_for_order,
    link_students_to_order, unlink_student_from_order,
    get_all_departments, update_student,
)
from db import get_connection
from ui.base_screen import BaseScreen
from ui.widgets import make_section_header, make_primary_button


class OrderStudentsScreen(BaseScreen):
    """
    Sub-screen for managing students linked to a specific graduation order.
    """

    def __init__(self, parent, switch_callback) -> None:
        self._order: dict | None = None
        self._back_callback = None
        self._departments: list[dict] = []
        super().__init__(parent, switch_callback)

    def set_order(self, order: dict, back_callback) -> None:
        """
        Configure the screen for a specific order.
        Called from GraduationOrdersScreen before navigating here.
        """
        self._order = order
        self._back_callback = back_callback

    # =========================================================================
    # Build
    # =========================================================================

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Top banner ──────────────────────────────────────────────────────
        banner = ctk.CTkFrame(self, fg_color=AppColors.HEADER_BG, corner_radius=8)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        banner.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            banner,
            text="←  رجوع  /  Back",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=130,
            height=36,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color="transparent",
            hover_color=AppColors.NAV_HOVER_BG,
            text_color=AppColors.NAV_TEXT,
            anchor="w",
            command=self._go_back,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=8)

        self._banner_label = ctk.CTkLabel(
            banner,
            text="",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SUBHEADING,
                weight="bold",
            ),
            anchor="e",
        )
        self._banner_label.grid(row=0, column=1, sticky="e", padx=(0, 20), pady=8)

        # ── Left: linked students ────────────────────────────────────────────
        left = ctk.CTkFrame(self, corner_radius=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        make_section_header(left, "الطلاب المرتبطون", "Linked Students").grid(
            row=0, column=0, sticky="e", padx=12, pady=(10, 6)
        )

        self._linked_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._linked_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._linked_scroll.grid_columnconfigure(0, weight=1)

        # ── Right: search + results ──────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        make_section_header(right, "إضافة طلاب", "Add Students").grid(
            row=0, column=0, sticky="e", padx=12, pady=(10, 6)
        )

        # Filter row
        filter_row = ctk.CTkFrame(right, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        filter_row.grid_columnconfigure(2, weight=1)

        # Dept filter
        self._dept_var = ctk.StringVar(value="كل الأقسام")
        self._dept_menu = ctk.CTkOptionMenu(
            filter_row,
            variable=self._dept_var,
            values=["كل الأقسام"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=180,
            height=30,
            command=lambda _: self._do_search(),
        )
        self._dept_menu.grid(row=0, column=0, padx=(0, 6))

        # Year filter
        self._year_var = ctk.StringVar(value="كل السنوات")
        self._year_entry = ctk.CTkOptionMenu(
            filter_row,
            variable=self._year_var,
            values=["كل السنوات"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=130,
            height=30,
            command=lambda _: self._do_search(),
        )
        self._year_entry.grid(row=0, column=1, padx=(0, 6))

        # Name search
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._do_search())
        ctk.CTkEntry(
            filter_row,
            textvariable=self._search_var,
            placeholder_text="بحث بالاسم  —  Search by name...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            height=30,
            justify="right",
        ).grid(row=0, column=2, sticky="ew")

        # "Auto-link matching" button
        make_primary_button(
            right, "🔗 ربط تلقائي", "Auto-Link Matching",
            command=self._auto_link,
        ).grid(row=2, column=0, sticky="e", padx=8, pady=(0, 6))

        self._search_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._search_scroll.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._search_scroll.grid_columnconfigure(0, weight=1)

    # =========================================================================
    # Refresh / load
    # =========================================================================

    def refresh(self) -> None:
        """Called each time the screen is raised."""
        if not self._order:
            return
        self._load_filter_options()
        self._update_banner()
        self._render_linked()
        self._do_search()

    def _update_banner(self) -> None:
        if not self._order:
            return
        o = self._order
        self._banner_label.configure(
            text=(f"أمر: {o['order_number']}  |  "
                  f"{o.get('dept_name_ar', '—')}  |  "
                  f"دفعة {o.get('admission_year', '—')}")
        )

    def _load_filter_options(self) -> None:
        self._departments = get_all_departments()
        dept_labels = ["كل الأقسام"] + [
            f"{d['name_ar']}  /  {d['name_en']}" for d in self._departments
        ]
        self._dept_menu.configure(values=dept_labels)
        self._dept_var.set("كل الأقسام")

        # Collect distinct years from students
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT admission_year FROM students ORDER BY admission_year DESC"
            ).fetchall()
        year_labels = ["كل السنوات"] + [str(r["admission_year"]) for r in rows]
        self._year_entry.configure(values=year_labels)
        self._year_var.set("كل السنوات")

    # =========================================================================
    # Linked students panel
    # =========================================================================

    def _render_linked(self) -> None:
        for w in self._linked_scroll.winfo_children():
            w.destroy()

        if not self._order:
            return

        rows = get_students_for_order(self._order["id"])
        if not rows:
            ctk.CTkLabel(
                self._linked_scroll,
                text="لا يوجد طلاب مرتبطون  —  No linked students",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED,
            ).grid(row=0, column=0, pady=20)
            return

        for i, row in enumerate(rows):
            self._add_linked_row(i, row)

    def _add_linked_row(self, idx: int, row: dict) -> None:
        bg = ("gray96", "gray20") if idx % 2 == 0 else ("white", "gray23")
        f = ctk.CTkFrame(self._linked_scroll, fg_color=bg, corner_radius=4)
        f.grid(row=idx, column=0, sticky="ew", pady=1)
        f.grid_columnconfigure(0, weight=1)

        avg_text = f"معدل {row['average']}" if row.get("average") else "—"
        ctk.CTkLabel(
            f,
            text=f"{row['full_name_ar']}  —  {avg_text}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(4, 8), pady=4)

        ctk.CTkButton(
            f,
            text="إلغاء الربط\nUnlink",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            width=70,
            height=30,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color=AppColors.COLOR_WARNING,
            hover_color="#E65100",
            command=lambda sid=row["id"]: self._unlink_student(sid),
        ).grid(row=0, column=1, padx=(4, 4), pady=4)

    # =========================================================================
    # Search results panel
    # =========================================================================

    def _do_search(self) -> None:
        for w in self._search_scroll.winfo_children():
            w.destroy()

        dept_label = self._dept_var.get()
        dept_id = None
        if dept_label != "كل الأقسام":
            for d in self._departments:
                if f"{d['name_ar']}  /  {d['name_en']}" == dept_label:
                    dept_id = d["id"]
                    break

        year_str = self._year_var.get()
        year = int(year_str) if year_str != "كل السنوات" and year_str.isdigit() else None

        name = self._search_var.get()
        rows = search_students_for_order(
            name_query=name,
            admission_year=year,
            department_id=dept_id,
            limit=50,
        )

        if not rows:
            ctk.CTkLabel(
                self._search_scroll,
                text="لا توجد نتائج  —  No results",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED,
            ).grid(row=0, column=0, pady=20)
            return

        for i, row in enumerate(rows):
            self._add_search_row(i, row)

    def _add_search_row(self, idx: int, row: dict) -> None:
        bg = ("gray96", "gray20") if idx % 2 == 0 else ("white", "gray23")
        f = ctk.CTkFrame(self._search_scroll, fg_color=bg, corner_radius=4)
        f.grid(row=idx, column=0, sticky="ew", pady=1)
        f.grid_columnconfigure(0, weight=1)

        already_linked = row.get("order_id") == (self._order["id"] if self._order else None)
        status = "✅" if already_linked else ""
        dept_text = row.get("dept_name_ar", "—")
        info = f"{row['full_name_ar']}  ({dept_text}، {row.get('admission_year', '—')}) {status}"

        ctk.CTkLabel(
            f,
            text=info,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="e",
            wraplength=250,
        ).grid(row=0, column=0, sticky="e", padx=(4, 8), pady=4)

        if not already_linked:
            ctk.CTkButton(
                f,
                text="ربط\nLink",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                width=60,
                height=30,
                corner_radius=AppSizes.CORNER_RADIUS_BTN,
                fg_color=AppColors.ACCENT_BLUE,
                hover_color="#1565C0",
                command=lambda sid=row["id"]: self._link_student(sid),
            ).grid(row=0, column=1, padx=4, pady=4)

    # =========================================================================
    # Actions
    # =========================================================================

    def _link_student(self, student_id: int) -> None:
        if not self._order:
            return
        update_student(
            student_id,
            order_id=self._order["id"],
            graduation_date=self._order.get("order_date"),
            graduation_semester=self._order.get("graduation_semester"),
        )
        self._render_linked()
        self._do_search()

    def _unlink_student(self, student_id: int) -> None:
        unlink_student_from_order(student_id)
        self._render_linked()
        self._do_search()

    def _auto_link(self) -> None:
        if not self._order:
            return
        linked = link_students_to_order(self._order["id"])
        self.show_error(
            f"تم ربط {linked} طالب تلقائياً بهذا الأمر.\n"
            f"Auto-linked {linked} students to this order."
        )
        self._render_linked()
        self._do_search()

    def _go_back(self) -> None:
        if self._back_callback:
            self._back_callback()
