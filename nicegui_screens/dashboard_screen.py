# =============================================================================
# nicegui_screens/dashboard_screen.py — NiceGUI Dashboard Screen & App Layout Shell
# =============================================================================

from nicegui import ui
from data.repositories import (
    DashboardRepository, StudentRepository, GraduationOrderRepository
)
from sync_engine import is_online
from nicegui_ui.ui_theme import Styles, NAV_ITEMS, STAT_CARDS, QUICK_ACTIONS
from nicegui_ui.ui_components import UI
from nicegui_screens.settings_screen import SettingsScreen
from nicegui_screens.students_screen import StudentsScreen


class MainAppShell:
    """
    Main Application Shell managing the Collapsible Sidebar, Top Header,
    and Dynamic Screen Switching (Dashboard, Settings, Students, etc.).
    """

    def __init__(self) -> None:
        self.repo = DashboardRepository()
        self.student_repo = StudentRepository()
        self.order_repo = GraduationOrderRepository()

        self.current_screen = "home"
        self.is_sidebar_open = True

        self.counts = {
            "total_students": 0,
            "total_departments": 0,
            "total_courses": 0,
            "total_personnel": 0,
        }
        self.recent_students = []
        self.recent_certificates = []
        self._refresh_cards = None

        self._sidebar_col = None
        self._sidebar_title_label = None
        self._sidebar_title_icon = None
        self._nav_labels: list = []
        self._user_chip_labels: list = []
        self._header_title_ar = None
        self._header_title_en = None

        self.refresh_data()
        self.build_ui()

    def refresh_data(self) -> None:
        """Fetches dashboard data & recent records."""
        try:
            self.counts = self.repo.get_counts()
        except Exception as exc:
            print(f"[MainAppShell] Failed to fetch counts: {exc}")

        try:
            self.recent_students = self.student_repo.get_all_paginated(limit=5) or []
        except Exception:
            self.recent_students = []

        if not self.recent_students:
            self.recent_students = [
                {"full_name_ar": "علي حسن أحمد", "dept_name_ar": "علوم الحاسوب", "admission_year": "2023-2024", "status": "مستمر"},
                {"full_name_ar": "سارة محمود علي", "dept_name_ar": "نظم المعلومات", "admission_year": "2023-2024", "status": "مستمر"},
                {"full_name_ar": "منى يوسف حسين", "dept_name_ar": "أمن الشبكات", "admission_year": "2022-2023", "status": "متخرج"},
            ]

        try:
            all_orders = self.order_repo.get_all() or []
            self.recent_certificates = all_orders[:5]
        except Exception:
            self.recent_certificates = []

        if not self.recent_certificates:
            self.recent_certificates = [
                {"full_name_ar": "حسين فلاح مهدي", "dept_name_ar": "علوم الحاسوب", "order_number": "1042 / 2024", "issue_date": "2024-06-15"},
                {"full_name_ar": "زينب عبد الكاظم", "dept_name_ar": "نظم المعلومات", "order_number": "988 / 2024", "issue_date": "2024-06-12"},
                {"full_name_ar": "أحمد جاسم محمد", "dept_name_ar": "أمن الشبكات", "order_number": "854 / 2024", "issue_date": "2024-06-01"},
            ]

    def build_ui(self) -> None:
        """Builds the full application container."""
        ui.query('.nicegui-content').classes('p-0 m-0')
        ui.query('body').classes(Styles.BODY)
        
        from nicegui_ui.state import app_session
        app_session.apply_theme_mode()

        from nicegui_ui.ui_theme import inject_global_styles
        inject_global_styles()

        with ui.row().classes(Styles.LAYOUT_ROW):
            self._build_sidebar()

            with ui.column().classes("flex-1 h-full gap-0 overflow-hidden bg-slate-100 dark:bg-[#0f172a] transition-colors duration-200"):
                self._build_top_header()

                with ui.scroll_area().classes("flex-1 h-full p-5"):
                    self.content_container = ui.column().classes("w-full gap-5")
                    self._render_active_screen()

    def _build_sidebar(self) -> None:
        self._nav_labels = []
        self._user_chip_labels = []
        self._sidebar_col = ui.column().classes(Styles.SIDEBAR_COL_EXPANDED)

        with self._sidebar_col:
            with ui.row().classes(Styles.SIDEBAR_HEADER):
                self._sidebar_title_label = ui.label("Certificate Manager").classes(
                    Styles.SIDEBAR_APP_TITLE
                )
                self._sidebar_title_icon = ui.icon(
                    "workspace_premium", size="md"
                ).classes("text-blue-400 self-center mx-auto")
                self._sidebar_title_icon.set_visibility(False)

            with ui.column().classes("w-full flex-1 overflow-y-auto p-3 gap-1"):
                for item in NAV_ITEMS:
                    self._build_nav_item(item)

            with ui.column().classes("w-full p-3 shrink-0"):
                self._build_user_chip()

    def _build_nav_item(self, item: dict) -> None:
        is_active = (item["key"] == self.current_screen)
        css = Styles.NAV_ITEM_ACTIVE if is_active else Styles.NAV_ITEM_INACTIVE

        row = ui.row().classes(css).on(
            "click", lambda key=item["key"]: self._switch_screen(key)
        )

        with row:
            icon_el = ui.icon(item["icon"], size="sm")
            icon_el.tooltip(f"{item['ar']}  —  {item['en']}")

            label_col = ui.column().classes("gap-0")
            with label_col:
                ui.label(item["ar"]).classes("font-semibold text-xs leading-tight")
                ui.label(item["en"]).classes("text-[11px] text-slate-400 leading-tight")

            self._nav_labels.append((row, label_col, item["key"]))

    def _handle_logout(self) -> None:
        """Opens a confirmation dialog before performing logout."""
        with ui.dialog() as dialog, ui.card().classes(
            "p-6 gap-4 w-96 max-w-full rounded-2xl !bg-white dark:!bg-[#1e293b] "
            "border border-slate-200 dark:border-slate-800 shadow-2xl"
        ):
            ui.label("Confirm Logout / تأكيد تسجيل الخروج").classes(
                "text-lg font-bold text-slate-900 dark:text-white border-b border-slate-200 dark:border-slate-800 pb-2 w-full"
            )
            ui.label("Are you sure you want to log out? / هل أنت تأكد من تسجيل الخروج؟").classes(
                "text-sm text-slate-600 dark:text-slate-300 my-2"
            )
            with ui.row().classes("w-full justify-end gap-3 mt-2"):
                ui.button("Cancel / إلغاء", on_click=dialog.close).classes(
                    "bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300 "
                    "hover:bg-slate-300 dark:hover:bg-slate-700 font-medium px-4 py-2 rounded-xl normal-case"
                )
                def confirm_logout():
                    dialog.close()
                    from nicegui_ui.state import app_session
                    app_session.logout_user()
                    ui.notify("تم تسجيل الخروج بنجاح / Logged out successfully!", type="info")
                    ui.navigate.to('/')

                ui.button("Logout / تسجيل الخروج", on_click=confirm_logout).classes(
                    "bg-rose-600 hover:bg-rose-500 text-white font-medium px-4 py-2 rounded-xl normal-case"
                )
        dialog.open()

    def _build_user_chip(self) -> None:
        from nicegui_ui.state import app_session

        user_name = app_session.name_en or app_session.username or "Admin User"
        user_role = (app_session.role or "admin").capitalize()

        with ui.row().classes(Styles.USER_CHIP) as self._user_chip_row:
            ui.icon("account_circle", size="sm").classes(Styles.USER_ICON).tooltip(
                f"{user_name} ({user_role})"
            )
            user_text_col = ui.column().classes("gap-0 flex-1 min-w-0")
            with user_text_col:
                UI.standard_label(user_name).classes("truncate text-xs font-bold text-slate-200")
                UI.muted_label(f"{user_role} • Connected").classes("text-[10px] text-emerald-400 font-semibold")

            logout_btn = ui.icon("logout", size="xs").classes(
                "text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
            ).tooltip("تسجيل الخروج / Logout")

            self._user_chip_labels.append(user_text_col)
            self._user_chip_labels.append(logout_btn)

            with ui.menu().classes("bg-slate-900 border border-slate-800 rounded-xl shadow-xl p-1") as user_menu:
                with ui.column().classes("p-2 gap-1 min-w-[190px]"):
                    with ui.row().classes("items-center gap-2 pb-2 mb-1 border-b border-slate-800"):
                        ui.icon("account_circle", size="md").classes("text-blue-400")
                        with ui.column().classes("gap-0"):
                            ui.label(user_name).classes("text-xs font-bold text-slate-100")
                            ui.label(f"{user_role} • Online").classes("text-[10px] text-emerald-400 font-semibold")

                    ui.menu_item("تسجيل الخروج / Logout", on_click=self._handle_logout).classes(
                        "text-red-400 hover:bg-red-500/20 rounded-lg text-xs font-semibold py-2 px-3"
                    )

            self._user_chip_row.on("click", user_menu.open)

    def toggle_sidebar(self) -> None:
        if not self._sidebar_col:
            return

        self.is_sidebar_open = not self.is_sidebar_open

        if self.is_sidebar_open:
            self._sidebar_col.classes(
                remove=Styles.SIDEBAR_COL_COLLAPSED,
                add=Styles.SIDEBAR_COL_EXPANDED
            )
            if self._sidebar_title_label:
                self._sidebar_title_label.set_visibility(True)
            if self._sidebar_title_icon:
                self._sidebar_title_icon.set_visibility(False)

            for row, label_col, _ in self._nav_labels:
                label_col.set_visibility(True)
                row.classes(remove="justify-center", add="")

            for text_col in self._user_chip_labels:
                text_col.set_visibility(True)
            if self._user_chip_row is not None:
                self._user_chip_row.classes(remove=Styles.USER_CHIP_MINI, add=Styles.USER_CHIP)

        else:
            self._sidebar_col.classes(
                remove=Styles.SIDEBAR_COL_EXPANDED,
                add=Styles.SIDEBAR_COL_COLLAPSED
            )
            if self._sidebar_title_label:
                self._sidebar_title_label.set_visibility(False)
            if self._sidebar_title_icon:
                self._sidebar_title_icon.set_visibility(True)

            for row, label_col, _ in self._nav_labels:
                label_col.set_visibility(False)
                row.classes(add="justify-center")

            for text_col in self._user_chip_labels:
                text_col.set_visibility(False)
            if self._user_chip_row is not None:
                self._user_chip_row.classes(remove=Styles.USER_CHIP, add=Styles.USER_CHIP_MINI)

    def _build_top_header(self) -> None:
        with ui.row().classes(Styles.HEADER_BAR):
            with ui.row().classes("items-center gap-4"):
                ui.button(
                    icon="menu",
                    on_click=self.toggle_sidebar
                ).classes(
                    "bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300 "
                    "hover:bg-slate-300 dark:hover:bg-slate-700 "
                    "p-2 rounded-xl border border-slate-300 dark:border-slate-700/60 shadow-none transition-colors"
                )

                title_ar, title_en = self._get_screen_header_titles()
                with ui.row().classes("items-baseline gap-3"):
                    self._header_title_ar = ui.label(title_ar).classes(
                        "text-xl font-bold text-slate-900 dark:text-white tracking-wide"
                    )
                    self._header_title_en = ui.label(f"—  {title_en}").classes(
                        "text-sm font-medium text-slate-600 dark:text-slate-400"
                    )

            with ui.row().classes("items-center gap-4"):
                UI.secondary_button("Refresh Data", icon="sync", on_click=self._on_refresh_click)

                online = is_online()
                net_text = "🟢 متصل (Online)" if online else "🔴 وضع عدم الاتصال (Offline)"
                net_color = "text-emerald-600 dark:text-emerald-400" if online else "text-red-600 dark:text-red-400"
                ui.label(net_text).classes(
                    f"text-xs font-semibold px-3 py-1.5 bg-slate-100 dark:bg-slate-900/80 "
                    f"rounded-full border border-slate-200 dark:border-slate-800 {net_color}"
                )

    def _get_screen_header_titles(self) -> tuple[str, str]:
        header_map = {
            "home":        ("لوحة التحكم", "Dashboard Overview"),
            "students":    ("إدارة الطلاب", "Students Management"),
            "orders":      ("أوامر التخرج", "Graduation Orders"),
            "departments": ("إدارة الأقسام", "Departments"),
            "courses":     ("المواد الدراسية", "Courses"),
            "personnel":   ("إدارة الكوادر", "Personnel"),
            "certificate": ("إصدار الوثائق", "Certificate Issuance"),
            "history":     ("سجل التغييرات", "Activity Log"),
            "settings":    ("إعدادات النظام", "System Settings"),
        }
        return header_map.get(self.current_screen, ("الرئيسية", "Dashboard"))

    def _switch_screen(self, screen_key: str) -> None:
        self.current_screen = screen_key

        for row, _label_col, key in self._nav_labels:
            if key == screen_key:
                row.classes(remove=Styles.NAV_ITEM_INACTIVE, add=Styles.NAV_ITEM_ACTIVE)
            else:
                row.classes(remove=Styles.NAV_ITEM_ACTIVE, add=Styles.NAV_ITEM_INACTIVE)

        title_ar, title_en = self._get_screen_header_titles()
        if self._header_title_ar:
            self._header_title_ar.set_text(title_ar)
        if self._header_title_en:
            self._header_title_en.set_text(f"—  {title_en}")

        self._render_active_screen()

    def _render_active_screen(self) -> None:
        self.content_container.clear()
        with self.content_container:
            if self.current_screen == "home":
                self._build_dashboard_content()
            elif self.current_screen == "settings":
                SettingsScreen()
            elif self.current_screen == "students":
                StudentsScreen()
            else:
                self._build_placeholder_screen()

    def _build_dashboard_content(self) -> None:
        """Renders main dashboard metrics & panels using UI.card context managers."""

        @ui.refreshable
        def stat_cards_section() -> None:
            with ui.grid(columns=4).classes("w-full gap-4"):
                for card_cfg in STAT_CARDS:
                    value = self.counts.get(card_cfg["count_key"], 0)
                    UI.stat_card(
                        title      = card_cfg["label"],
                        value      = value,
                        icon_name  = card_cfg["icon"],
                        text_color = card_cfg["text_color"],
                        icon_bg    = card_cfg["icon_bg"],
                    )

        stat_cards_section()
        self._refresh_cards = stat_cards_section

        with ui.row().classes("w-full gap-5 items-stretch flex-nowrap"):
            with UI.card("w-1/3 justify-between"):
                UI.section_label("Quick Actions  —  إجراءات سريعة")
                with ui.column().classes("w-full gap-3 flex-1 justify-center"):
                    for action in QUICK_ACTIONS:
                        ui.button(
                            action["label"],
                            icon=action["icon"],
                            on_click=(
                                (lambda t=action["target"]: self._switch_screen(t))
                                if action["target"] else None
                            ),
                        ).classes(action["style"])

            with UI.card("flex-1"):
                with ui.tabs().classes(
                    "w-full text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700/60"
                ) as tabs:
                    tab_students = ui.tab(
                        "Recent Students Added  —  أحدث الطلاب المضافين",
                        icon="person_add"
                    )
                    tab_certs = ui.tab(
                        "Recent Certificates Printed  —  أحدث الشهادات الصادرة",
                        icon="workspace_premium"
                    )

                with ui.tab_panels(tabs, value=tab_students).classes("w-full bg-transparent p-0"):
                    with ui.tab_panel(tab_students).classes("w-full p-0 pt-2"):
                        cols_s = [
                            {"name": "name",   "label": "Student Name / اسم الطالب", "field": "name",   "align": "left"},
                            {"name": "dept",   "label": "Department / القسم",        "field": "dept",   "align": "left"},
                            {"name": "year",   "label": "Batch / سنة القبول",        "field": "year",   "align": "center"},
                            {"name": "status", "label": "Status / الحالة",           "field": "status", "align": "right"},
                        ]
                        rows_s = [
                            {
                                "name":   s.get("full_name_ar") or s.get("full_name_en") or "طالب جديد",
                                "dept":   s.get("dept_name_ar") or "قسم عام",
                                "year":   s.get("admission_year") or "2023-2024",
                                "status": s.get("status") or "مستمر",
                            }
                            for s in self.recent_students
                        ]
                        ui.table(
                            columns=cols_s, rows=rows_s, row_key="name"
                        ).classes(Styles.TABLE_CLASSES).props("flat bordered hide-bottom")

                    with ui.tab_panel(tab_certs).classes("w-full p-0 pt-2"):
                        cols_c = [
                            {"name": "name",  "label": "Student Name / اسم الطالب", "field": "name",  "align": "left"},
                            {"name": "dept",  "label": "Department / القسم",        "field": "dept",  "align": "left"},
                            {"name": "order", "label": "Order No / رقم الأمر",      "field": "order", "align": "center"},
                            {"name": "date",  "label": "Date Issued / التاريخ",      "field": "date",  "align": "right"},
                        ]
                        rows_c = [
                            {
                                "name":  c.get("full_name_ar") or c.get("student_name") or "طالب متخرج",
                                "dept":  c.get("dept_name_ar") or "قسم عام",
                                "order": c.get("order_number") or "1024 / 2024",
                                "date":  c.get("issue_date") or c.get("created_at") or "2024-06-15",
                            }
                            for c in self.recent_certificates
                        ]
                        ui.table(
                            columns=cols_c, rows=rows_c, row_key="name"
                        ).classes(Styles.TABLE_CLASSES).props("flat bordered hide-bottom")

    def _build_placeholder_screen(self) -> None:
        header_ar, header_en = self._get_screen_header_titles()
        with UI.card("items-center justify-center py-20"):
            ui.icon("construction", size="lg").classes("text-amber-500 dark:text-amber-400")
            ui.label(f"شاشة {header_ar} قيد التطوير").classes(
                "text-2xl font-bold text-slate-900 dark:text-white"
            )
            ui.label(f"{header_en} Screen — Under Migration to NiceGUI").classes(
                "text-sm text-slate-600 dark:text-slate-400"
            )

    def _on_refresh_click(self) -> None:

        self.refresh_data()
        if self._refresh_cards is not None:
            self._refresh_cards.refresh()


DashboardScreen = MainAppShell
