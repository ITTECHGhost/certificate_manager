# =============================================================================
# nicegui_screens/dashboard_screen.py — NiceGUI Dashboard Screen & App Layout Shell
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
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

            with ui.column().classes("app-main-area flex-1 h-full gap-0 overflow-hidden"):
                self._build_top_header()

                with ui.scroll_area().classes("flex-1 h-full p-5"):
                    self.content_container = ui.column().classes("w-full gap-5")
                    self._render_active_screen()

        # Start periodic background network status polling loop (every 5 seconds)
        ui.timer(5.0, self._check_network_loop)

    async def _check_network_loop(self) -> None:
        """Periodically checks FastAPI reachability and automatically updates live online/offline indicators."""
        from nicegui import run
        from sync_engine import (
            check_network_status, set_online, is_online,
            sync_offline_queue_to_mysql
        )

        prev_online = is_online()
        now_online = bool(await run.io_bound(check_network_status))
        set_online(now_online)

        # Unconditionally refresh live status indicators in DOM using .refresh()
        if hasattr(self, '_refresh_status') and self._refresh_status:
            self._refresh_status.refresh()
        if hasattr(self, '_header_status') and self._header_status:
            self._header_status.refresh()

        if now_online and not prev_online:
            try:
                await run.io_bound(sync_offline_queue_to_mysql)
            except Exception as exc:
                print(f"[MainAppShell] Sync error on reconnection: {exc}")

    async def _on_refresh_click(self) -> None:
        """Refreshes network status, dashboard metrics, and UI components on demand."""
        from nicegui import run
        from sync_engine import check_network_status, set_online

        now_online = bool(await run.io_bound(check_network_status))
        set_online(now_online)

        if hasattr(self, '_refresh_status') and self._refresh_status:
            self._refresh_status.refresh()
        if hasattr(self, '_header_status') and self._header_status:
            self._header_status.refresh()

        self.refresh_data()
        if self._refresh_cards:
            self._refresh_cards.refresh()
        ui.notify("تم تحديث البيانات / Data refreshed!", type="info")

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
                ).classes("app-text-accent self-center mx-auto")
                self._sidebar_title_icon.set_visibility(False)

            with ui.column().classes(Styles.SIDEBAR_NAV_GROUP):
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
                ui.label(item["ar"]).classes("nav-title-ar font-bold text-sm leading-tight")
                ui.label(item["en"]).classes("nav-title-en font-normal text-xs leading-tight")

            self._nav_labels.append((row, label_col, item["key"]))

    def _handle_logout(self) -> None:
        """Displays a modal confirmation dialog before logging out the active user."""
        with ui.dialog() as dialog, UI.card():
            dialog_card_classes = "p-6 gap-4 min-w-[340px] max-w-sm rounded-2xl"
            
            with ui.column().classes(dialog_card_classes):
                with ui.row().classes("items-center gap-3 w-full border-b pb-3"):
                    ui.icon("logout", size="md").classes("app-text-danger")
                    with ui.column().classes("gap-0"):
                        ui.label("تأكيد تسجيل الخروج").classes("app-text-primary text-base font-bold")
                        ui.label("Logout Confirmation").classes("app-text-muted text-xs")

                ui.label("هل أنت تأكد من رغبتك في تسجيل الخروج؟").classes("app-text-primary text-sm font-semibold mt-2")
                ui.label("Are you sure you want to log out?").classes("app-text-muted text-xs mb-2")

                with ui.row().classes("w-full justify-end gap-3 pt-2 border-t"):
                    UI.ghost_button("إلغاء / Cancel", on_click=dialog.close).classes("px-4 py-2 text-xs")
                    
                    def _confirm():
                        dialog.close()
                        from nicegui_ui.state import app_session
                        app_session.logout_user()
                        ui.notify("تم تسجيل الخروج بنجاح / Logged out successfully!", type="info")
                        ui.navigate.to("/")

                    UI.danger_button("تسجيل الخروج / Logout", icon="logout", on_click=_confirm).classes("px-4 py-2 text-xs font-bold")

        dialog.open()

    def _build_user_chip(self) -> None:
        from nicegui_ui.state import app_session
        user_name = app_session.name_en or app_session.username or "Admin User"
        user_role = (app_session.role or "admin").capitalize()

        self._chip_expanded = "w-full items-center gap-3 p-3 rounded-2xl border cursor-pointer transition-all bg-slate-800/60 dark:bg-[#131C35] border-slate-700/60 dark:border-slate-700 hover:bg-slate-800 dark:hover:bg-slate-800/80"
        self._chip_mini = "w-full justify-center p-3 rounded-2xl border cursor-pointer transition-all bg-slate-800/60 dark:bg-[#131C35] border-slate-700/60 dark:border-slate-700 hover:bg-slate-800 dark:hover:bg-slate-800/80"

        with ui.row().classes(self._chip_expanded) as self._user_chip_row:
            with ui.element("div").classes("w-10 h-10 shrink-0 rounded-full bg-blue-600 dark:bg-blue-500 flex items-center justify-center text-white font-bold text-sm"):
                ui.label("SA")
                
            user_text_col = ui.column().classes("gap-0 flex-1 min-w-0")
            with user_text_col:
                ui.label(user_name).classes("truncate text-sm font-bold text-slate-100")
                
                @ui.refreshable
                def status_indicator():
                    from sync_engine import is_online
                    online = is_online()
                    color = "text-emerald-400" if online else "text-red-400"
                    dot = "🟢" if online else "🔴"
                    text = "متصل / Online" if online else "غير متصل / Offline"
                    ui.label(f"{dot} {text}").classes(f"text-[10px] {color} font-semibold")
                
                status_indicator()
                self._refresh_status = status_indicator

            logout_btn = ui.icon("logout", size="xs").classes(
                "text-slate-400 hover:text-slate-200 dark:text-slate-400 dark:hover:text-slate-200 cursor-pointer transition-colors ml-auto"
            )
            logout_btn.on("click", self._handle_logout)
            logout_btn.tooltip("تسجيل الخروج / Logout")

            self._user_chip_row.on("click", self._handle_logout)

            self._user_chip_labels.append(user_text_col)
            self._user_chip_labels.append(logout_btn)

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
                self._user_chip_row.classes(remove=getattr(self, '_chip_mini', ''), add=getattr(self, '_chip_expanded', ''))

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
                self._user_chip_row.classes(remove=getattr(self, '_chip_expanded', ''), add=getattr(self, '_chip_mini', ''))

    def _build_top_header(self) -> None:
        with ui.row().classes(Styles.HEADER_BAR):
            with ui.row().classes("items-center gap-4"):
                ui.button(
                    icon="menu",
                    on_click=self.toggle_sidebar
                ).classes("app-btn-icon p-2 rounded-xl shadow-none")

                title_ar, title_en = self._get_screen_header_titles()
                with ui.row().classes("items-baseline gap-3"):
                    self._header_title_ar = ui.label(title_ar).classes(
                        "app-text-primary text-xl font-bold tracking-wide"
                    )
                    self._header_title_en = ui.label(f"—  {title_en}").classes(
                        "app-text-muted text-sm font-medium"
                    )

            with ui.row().classes("items-center gap-4"):
                @ui.refreshable
                def header_status_badge():
                    from sync_engine import is_online
                    online = is_online()
                    bg = (
                        "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/30"
                        if online else
                        "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/30"
                    )
                    dot = "🟢" if online else "🔴"
                    text = "متصل / Online" if online else "غير متصل / Offline"
                    ui.label(f"{dot} {text}").classes(f"px-3 py-1.5 rounded-xl border text-xs font-bold {bg}")
                header_status_badge()
                self._header_status = header_status_badge

                ui.button("تحديث البيانات / Refresh Data", icon="sync", on_click=self._on_refresh_click).classes(
                    "app-btn-refresh font-bold normal-case shadow-none px-4 py-2 text-sm"
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
            with ui.element("div").classes(Styles.STAT_GRID):
                for card_cfg in STAT_CARDS:
                    value = self.counts.get(card_cfg["count_key"], 0)
                    UI.stat_card(
                        title_ar   = card_cfg["label_ar"],
                        title_en   = card_cfg["label_en"],
                        value      = value,
                        icon_name  = card_cfg["icon"],
                        variant    = card_cfg["variant"],
                    )

        stat_cards_section()
        self._refresh_cards = stat_cards_section

        with ui.row().classes(Styles.BOTTOM_ROW):
            with ui.column().classes("app-card w-full xl:w-1/3 p-5 rounded-2xl gap-3 h-auto justify-start self-start"):
                UI.section_label("Quick Actions  —  إجراءات سريعة")
                with ui.column().classes("w-full gap-2.5 mt-1"):
                    for action in QUICK_ACTIONS:
                        action_row = ui.row().classes(
                            "app-action-item w-full items-center gap-3.5 px-4 py-3 rounded-xl cursor-pointer"
                        ).on(
                            "click",
                            (lambda t=action["target"]: self._switch_screen(t))
                            if action["target"] else None
                        )
                        with action_row:
                            ui.icon(action["icon"], size="sm").classes("app-sidebar-icon")
                            with ui.column().classes("gap-0 min-w-0 flex-1"):
                                ui.label(action["label_ar"]).classes("nav-title-ar font-bold text-sm leading-tight")
                                ui.label(action["label_en"]).classes("nav-title-en font-normal text-xs leading-tight")
                            ui.icon("arrow_back_ios", size="xs").classes("app-text-faint ml-auto opacity-60")

            with UI.card(Styles.TABLE_PANEL):
                with ui.tabs().classes("w-full app-tabs") as tabs:
                    tab_students = ui.tab(
                        "Recent Students Added  —  أحدث الطلاب المضافين",
                        icon="person_add"
                    )
                    tab_certs = ui.tab(
                        "Recent Certificates Printed  —  أحدث الشهادات الصادرة",
                        icon="workspace_premium"
                    )

                with ui.tab_panels(tabs, value=tab_students).classes("w-full p-0 bg-transparent"):
                    with ui.tab_panel(tab_students).classes("w-full p-0 pt-2 bg-transparent"):
                        cols_s = [
                            {"name": "name",   "label": "Student Name / اسم الطالب", "field": "name",   "align": "left", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "dept",   "label": "Department / القسم",        "field": "dept",   "align": "left", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "year",   "label": "Batch / سنة القبول",        "field": "year",   "align": "center", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "status", "label": "Status / الحالة",           "field": "status", "align": "right", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
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
                        s_table = ui.table(
                            columns=cols_s, rows=rows_s, row_key="name"
                        ).classes(Styles.TABLE_CLASSES).props("flat separator='horizontal'")
                        s_table.add_slot("body-cell-status", '''
                            <q-td :props="props">
                                <span v-if="props.value === 'مستمر'" class="text-emerald-600 dark:text-emerald-400 font-bold">{{ props.value }}</span>
                                <span v-else class="text-slate-700 dark:text-slate-300 font-semibold">{{ props.value }}</span>
                            </q-td>
                        ''')

                    with ui.tab_panel(tab_certs).classes("w-full p-0 pt-2 bg-transparent"):
                        cols_c = [
                            {"name": "name",  "label": "Student Name / اسم الطالب", "field": "name",  "align": "left", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "dept",  "label": "Department / القسم",        "field": "dept",  "align": "left", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "order", "label": "Order No / رقم الأمر",      "field": "order", "align": "center", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
                            {"name": "date",  "label": "Date Issued / التاريخ",      "field": "date",  "align": "right", "headerClasses": "text-slate-600 dark:text-slate-400 font-bold bg-transparent"},
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
                        ).classes(Styles.TABLE_CLASSES).props("flat separator='horizontal'")

    def _build_placeholder_screen(self) -> None:
        header_ar, header_en = self._get_screen_header_titles()
        with UI.card("items-center justify-center py-20"):
            ui.icon("construction", size="lg").classes("app-text-warning")
            ui.label(f"شاشة {header_ar} قيد التطوير").classes(
                "app-text-primary text-2xl font-bold"
            )
            ui.label(f"{header_en} Screen — Under Migration to NiceGUI").classes(
                "app-text-muted text-sm"
            )

DashboardScreen = MainAppShell
