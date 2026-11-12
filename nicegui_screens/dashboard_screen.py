import logging
import time
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/dashboard_screen.py — NiceGUI Dashboard Screen & App Layout Shell
#
# UI STRUCTURE & ARCHITECTURE:
#   1. MainAppShell Layout Wrapper (Root viewport row split into Sidebar + Main Area)
#   2. Collapsible Left Sidebar (App Title, Navigation Items, User Session Profile Chip)
#   3. Top Header Bar (Sidebar Menu Toggle Button, Dynamic Page Title, Network Status, Refresh Button)
#   4. Dynamic Content Area:
#      - Stat Metrics Grid (4 Stat Cards: Students, Departments, Courses, Personnel)
#      - Bottom Section (Split Row):
#        a. Quick Actions Card (Action Tile rows with navigation click handlers)
#        b. Tabbed Data Table Card (Recent Students Added & Recent Certificates Printed)
#   5. Logout Confirmation Modal Dialog
#
# Visual styling: CSS hook classes (app-*) defined in theme.css
# Layout styling: Tailwind structural classes (w-*, h-*, p-*, gap-*, flex, etc.)
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
from nicegui_screens.graduation_orders_screen import GraduationOrdersScreen
from nicegui_screens.courses_screen import CoursesScreen
from nicegui_screens.personnel_screen import PersonnelScreen
from nicegui_screens.certificate_screen import CertificateScreen
from nicegui_screens.issued_certificates_screen import IssuedCertificatesScreen


def _fmt_grad_date(value) -> str:
    """Graduation date as YYYY-MM-DD, or '—' when empty / the 1970 placeholder."""
    text = str(value or "").strip()[:10]
    if not text or text.startswith("1970-01-01") or text.lower() in ("none", "null"):
        return "—"
    return text


class MainAppShell:
    """
    Main Application Shell managing the Collapsible Sidebar, Top Header,
    and Dynamic Screen Switching (Dashboard, Settings, Students, etc.).
    """

    def __init__(self) -> None:
        # Data Access Layer Repositories
        self.repo = DashboardRepository()
        self.student_repo = StudentRepository()
        self.order_repo = GraduationOrderRepository()

        # Application Shell State
        self.current_screen = "home"
        self.is_sidebar_open = True

        # Metric Counts & Recent Data Caches
        self.counts = {
            "total_students": 0,
            "total_departments": 0,
            "total_issued": 0,
            "total_courses": 0,
            "total_personnel": 0,
        }
        self.recent_students = []
        self.recent_certificates = []
        self._refresh_cards = None

        # DOM Element References for Dynamic Updates
        self._sidebar_col = None
        self._sidebar_title_label = None
        self._sidebar_title_icon = None
        self._nav_labels: list = []
        self._user_chip_labels: list = []
        self._user_chip_row = None
        self._header_title_ar = None
        self._header_title_en = None

        # Initialize Data & Build Interface
        self.refresh_data()
        self.build_ui()

        # Once per run: offer a newer client version (now / at the next start / later)
        from nicegui_ui.update_prompt import check_at_start
        ui.timer(4.0, check_at_start, once=True)

    def refresh_data(self) -> None:
        """Fetches dashboard metrics & recent database records."""
        t0 = time.perf_counter()
        try:
            self.counts = self.repo.get_counts()
        except Exception as exc:
            log.warning(f"[MainAppShell] Failed to fetch counts: {exc}")

        # Issued total is not in the counts API and needs the whole report: _load_issued_count
        # fetches it in the background once the page is on screen; until then the tile shows a dash.
        self.counts.setdefault("total_issued", "—")

        # 1. Fetch recent students (from last added ID to the first)
        try:
            self.recent_students = self.student_repo.get_last_added_students(limit=5) or []
        except Exception as exc:
            log.warning(f"[MainAppShell] Failed to fetch recent students: {exc}")
            self.recent_students = []


        # 2. Fetch recent issued certificates (students linked to a graduation order)
        try:
            self.recent_certificates = self.student_repo.get_recent_issued_certificates(limit=5) or []
        except Exception as exc:
            log.warning(f"[MainAppShell] Failed to fetch recent certificates: {exc}")
            self.recent_certificates = []


        # 3. Fetch recent printed certificates
        try:
            self.recent_printed_certificates = self.student_repo.get_recent_printed_certificates(limit=5) or []
        except Exception as exc:
            log.warning(f"[MainAppShell] Failed to fetch printed certificates: {exc}")
            self.recent_printed_certificates = []

        if not self.recent_printed_certificates:
            self.recent_printed_certificates = list(self.recent_certificates)
        log.info("[perf] dashboard data loaded in %.0f ms", (time.perf_counter() - t0) * 1000)

    # =========================================================================
    # 1. ROOT LAYOUT CONTAINER DEFINITION
    # =========================================================================
    def build_ui(self) -> None:
        """
        [LAYOUT CONTAINER]
        Root layout: sidebar on the right (RTL), then a column with the header
        bar and the content area. Only the content area scrolls.
        """
        ui.query('.nicegui-content').classes('p-0 m-0')
        ui.query('body').classes(Styles.BODY)

        # Apply active user session theme & global CSS tokens
        from nicegui_ui.state import app_session
        app_session.load()
        app_session.apply_theme_mode()

        from nicegui_ui.ui_theme import inject_global_styles
        inject_global_styles()

        with ui.row().classes(Styles.LAYOUT_ROW):
            self._build_sidebar()

            with ui.column().classes("app-main-area flex-1 min-w-0 max-w-full h-full gap-0 no-wrap overflow-hidden"):
                self._build_top_header()

                # The one scroll container: native scrollbar, on the RTL side of the content
                with ui.element("div").classes("app-main-scroll w-full"):
                    self.content_container = ui.column().classes("app-page")
                    self._render_active_screen()

        # Start periodic background network status polling loop (every 5 seconds)
        ui.timer(5.0, self._check_network_loop)
    # =========================================================================
    # BACKGROUND TASKS & NETWORK POLLING
    # =========================================================================
    async def _check_network_loop(self) -> None:
        """Periodically checks network reachability and updates live indicators in DOM."""
        from nicegui import run
        from sync_engine import (
            check_network_status, set_online, is_online,
            sync_offline_queue_to_mysql, pull_mysql_to_sqlite_background, sync_result_message
        )

        prev_online = is_online()
        now_online = bool(await run.io_bound(check_network_status))
        set_online(now_online)

        # Every 5 minutes (60 x 5 s): pick up reference data changed on other laptops
        self._net_loop_count = getattr(self, "_net_loop_count", 0) + 1
        if now_online and prev_online and self._net_loop_count % 60 == 0:
            from sync_engine import refresh_replica_tables_background, LOCAL_FIRST_TABLES
            refresh_replica_tables_background(LOCAL_FIRST_TABLES)
            from data.repositories import IssuedCertificateRepository
            await run.io_bound(IssuedCertificateRepository().ensure_number_block)

        # Refresh DOM status badges
        if hasattr(self, '_refresh_status') and self._refresh_status:
            self._refresh_status.refresh()
        if hasattr(self, '_header_status') and self._header_status:
            self._header_status.refresh()

        if now_online and not prev_online:
            try:
                sync_result = await run.io_bound(sync_offline_queue_to_mysql)
                message = sync_result_message(sync_result)
                if message:
                    ui.notify(message[0], type=message[1], timeout=10000)
                pull_mysql_to_sqlite_background()
                from data.repositories import IssuedCertificateRepository
                await run.io_bound(IssuedCertificateRepository().ensure_number_block)
                import services.template_sync as t_sync
                await run.io_bound(t_sync.sync_templates_if_online)
            except Exception as exc:
                log.warning(f"[MainAppShell] Sync error on reconnection: {exc}")
        elif now_online and not getattr(self, "_startup_queue_checked", False):
            # Started while already online: send anything still waiting from an offline session
            self._startup_queue_checked = True
            try:
                from data.repositories import IssuedCertificateRepository
                await run.io_bound(IssuedCertificateRepository().ensure_number_block)
            except Exception as exc:
                log.debug(f"[MainAppShell] Certificate number block check: {exc}")
            try:
                from sync_engine import get_queue_status
                if get_queue_status().get("pending"):
                    sync_result = await run.io_bound(sync_offline_queue_to_mysql)
                    message = sync_result_message(sync_result)
                    if message:
                        ui.notify(message[0], type=message[1], timeout=10000)
            except Exception as exc:
                log.warning(f"[MainAppShell] Startup queue sync error: {exc}")

    async def _load_issued_count(self) -> None:
        """Counts issued certificates off the UI thread, then updates the stat tile."""
        from nicegui import run
        try:
            report = await run.io_bound(self.student_repo.get_issued_certificates_report)
            self.counts["total_issued"] = len(report or [])
        except Exception as exc:
            log.warning(f"[MainAppShell] Failed to count issued certificates: {exc}")
            return
        if self._refresh_cards and self.current_screen == "home":
            self._refresh_cards.refresh()

    async def _on_refresh_click(self) -> None:
        """
        [BUTTON HANDLER]
        Refreshes network connectivity status, metric counts, and table data.
        Triggered by the 'Refresh Data' button in the Header Bar.
        """
        from nicegui import run
        from sync_engine import check_network_status, set_online

        now_online = bool(await run.io_bound(check_network_status))
        set_online(now_online)

        if hasattr(self, '_refresh_status') and self._refresh_status:
            self._refresh_status.refresh()
        if hasattr(self, '_header_status') and self._header_status:
            self._header_status.refresh()

        if now_online:
            from sync_engine import refresh_replica_tables, LOCAL_FIRST_TABLES
            await run.io_bound(refresh_replica_tables, LOCAL_FIRST_TABLES)

        self.refresh_data()
        if self._refresh_cards:
            self._refresh_cards.refresh()
        await self._load_issued_count()
        ui.notify("تم تحديث البيانات", type="positive")

    # =========================================================================
    # 2. SIDEBAR
    # =========================================================================
    def _build_sidebar(self) -> None:
        """
        [SIDEBAR]
        Flat list of icon + Arabic label. The active item has a filled
        background and an accent bar. The toggle collapses it to icons.
        """
        self._nav_labels = []
        self._sidebar_col = ui.column().classes(Styles.SIDEBAR_COL_EXPANDED)

        with self._sidebar_col:
            with ui.row().classes(Styles.SIDEBAR_HEADER):
                self._sidebar_toggle_btn = UI.icon_button("menu", "طي القائمة", on_click=self.toggle_sidebar)
                self._sidebar_title_label = ui.column().classes("app-sidebar-titles gap-0 min-w-0")
                with self._sidebar_title_label:
                    ui.label("مدير الشهادات").classes(f"{Styles.SIDEBAR_APP_TITLE} truncate")
                self._sidebar_title_icon = None

            with ui.column().classes(Styles.SIDEBAR_NAV_GROUP):
                from nicegui_ui.state import app_session
                # Screens come from the access profile cached at login (no network call here)
                access = app_session.get_access()
                cached_screens = access.get("allowed_screens") if access else None
                if app_session.role == "admin" or not access or cached_screens is None:
                    allowed_screen_keys = {item["key"] for item in NAV_ITEMS}
                else:
                    allowed_screen_keys = set(cached_screens)

                allowed_screen_keys.add("home")
                allowed_screen_keys.add("profile")
                self.allowed_screens = allowed_screen_keys

                for item in NAV_ITEMS:
                    if item["key"] in allowed_screen_keys:
                        self._build_nav_item(item)

    def _build_nav_item(self, item: dict) -> None:
        """One sidebar row: icon + Arabic label; keyboard-focusable."""
        is_active = (item["key"] == self.current_screen)
        css = Styles.NAV_ITEM_ACTIVE if is_active else Styles.NAV_ITEM_INACTIVE

        row = ui.row().classes(f"{css} no-wrap").props('tabindex="0" role="link"')
        row.on("click", lambda key=item["key"]: self._switch_screen(key))
        row.on("keydown.enter", lambda key=item["key"]: self._switch_screen(key))

        with row:
            icon_el = ui.icon(item["icon"], size="20px")
            label_col = ui.label(item["ar"]).classes("nav-title-ar")
            # Shows beside the icon; mainly useful when the rail is collapsed
            icon_el.tooltip(item["ar"]).props("anchor='center left' self='center right'")

        self._nav_labels.append((row, label_col, item["key"]))

    def toggle_sidebar(self) -> None:
        """Collapse the sidebar to an icon rail, or expand it again."""
        if not self._sidebar_col:
            return
        self.is_sidebar_open = not self.is_sidebar_open
        if self.is_sidebar_open:
            self._sidebar_col.classes(remove=Styles.SIDEBAR_COL_COLLAPSED, add=Styles.SIDEBAR_COL_EXPANDED)
        else:
            self._sidebar_col.classes(remove=Styles.SIDEBAR_COL_EXPANDED, add=Styles.SIDEBAR_COL_COLLAPSED)
        if self._sidebar_title_label:
            self._sidebar_title_label.set_visibility(self.is_sidebar_open)
        for row, label_col, _ in self._nav_labels:
            label_col.set_visibility(self.is_sidebar_open)
            if self.is_sidebar_open:
                row.classes(remove="justify-center")
            else:
                row.classes(add="justify-center")

    # =========================================================================
    # 3. LOGOUT CONFIRMATION
    # =========================================================================
    def _handle_logout(self) -> None:
        from nicegui_ui.state import app_session

        def _confirm():
            app_session.logout_user()
            ui.notify("تم تسجيل الخروج", type="info")
            ui.navigate.to("/")

        UI.confirm_dialog(
            "تسجيل الخروج",
            "هل تريد تسجيل الخروج من البرنامج؟",
            "تسجيل الخروج",
            _confirm,
            danger=False,
        )

    # =========================================================================
    # 4. HEADER BAR
    # =========================================================================
    def _build_top_header(self) -> None:
        """
        [HEADER BAR]
        One row, one height: the page title on the start side; on the other
        side the sync dot, a refresh icon and the user chip (Profile, Logout).
        """
        with ui.row().classes(Styles.HEADER_BAR):
            self._header_title_ar = ui.label(self._get_screen_header_titles()[0]).classes("app-header-title min-w-0")
            self._header_title_en = None

            with ui.row().classes("items-center gap-2 no-wrap shrink-0"):
                @ui.refreshable
                def header_status_badge():
                    from sync_engine import is_online
                    online = is_online()
                    label = "متصل بالسيرفر" if online else "غير متصل، يعمل على هذا الجهاز"
                    dot = ui.element("span").classes("app-sync-dot" + ("" if online else " app-sync-dot--offline"))
                    dot.props(f'role="status" aria-label="{label}"')
                    dot.tooltip(label)

                header_status_badge()
                self._header_status = header_status_badge
                self._refresh_status = None

                UI.icon_button("refresh", "تحديث البيانات", on_click=self._on_refresh_click)
                self._build_topbar_user_card()

    def _build_topbar_user_card(self) -> None:
        """User chip: avatar + name; its menu holds Profile and Logout."""
        from nicegui_ui.state import app_session
        user_name = app_session.name_ar or app_session.name_en or app_session.username or "مدير النظام"
        initials = "".join(part[0] for part in user_name.split() if part)[:2] or "م"

        with ui.row().classes("app-user-chip items-center no-wrap").props('tabindex="0" role="button" aria-haspopup="menu"') as chip:
            with ui.element("div").classes("app-user-avatar"):
                ui.label(initials.upper())
            ui.label(user_name).classes("app-user-name truncate max-w-[140px]")
            ui.icon("expand_more", size="18px").classes("app-text-muted")
            with ui.menu().props("anchor='bottom left' self='top left'") as menu:
                ui.menu_item("الملف الشخصي", on_click=lambda: self._switch_screen("profile"))
                ui.separator()
                ui.menu_item("تسجيل الخروج", on_click=self._handle_logout)
        chip.on("keydown.enter", menu.open)

    def _get_screen_header_titles(self) -> tuple[str, str]:
        """Arabic page title for the active screen (the second value is always empty)."""
        header_map = {
            "home":         "الرئيسية",
            "students":     "الطلاب",
            "orders":       "أوامر التخرج",
            "courses":      "المواد الدراسية",
            "personnel":    "الكوادر",
            "certificate":  "إصدار كتاب",
            "issued_certs": "سجل الوثائق الصادرة",
            "reports":      "تقارير الطلاب",
            "history":      "سجل التغييرات",
            "settings":     "الإعدادات",
            "profile":      "الملف الشخصي",
        }
        return header_map.get(self.current_screen, "الرئيسية"), ""

    def _switch_screen(self, screen_key: str, defer: bool = True) -> None:
        """Handles navigation between screens when a sidebar button is clicked."""
        if screen_key != "profile" and hasattr(self, "allowed_screens") and self.allowed_screens and screen_key not in self.allowed_screens:
            ui.notify("ليس لديك صلاحية لفتح هذه الشاشة", type="warning")
            return

        self.current_screen = screen_key

        for row, _label_col, key in self._nav_labels:
            if key == screen_key:
                row.classes(remove=Styles.NAV_ITEM_INACTIVE, add=Styles.NAV_ITEM_ACTIVE)
            else:
                row.classes(remove=Styles.NAV_ITEM_ACTIVE, add=Styles.NAV_ITEM_INACTIVE)

        if self._header_title_ar:
            self._header_title_ar.set_text(self._get_screen_header_titles()[0])

        self._render_active_screen(defer=defer)

    def _render_active_screen(self, defer: bool = True) -> None:
        """Shows a skeleton at once, then builds the page on the next tick (a newer switch wins)."""
        self._render_token = getattr(self, "_render_token", 0) + 1
        if not defer:
            self._build_active_screen(self._render_token)
            return
        token = self._render_token
        self.content_container.clear()
        with self.content_container:
            UI.skeleton(rows=6, height=44)
            ui.timer(0.01, lambda: self._build_active_screen(token), once=True)

    def _build_active_screen(self, token: int) -> None:
        """Clears and re-populates the main content viewport with the active screen component."""
        if token != self._render_token:
            return
        t0 = time.perf_counter()
        self.content_container.clear()
        with self.content_container:
            if self.current_screen == "home":
                self._build_dashboard_content()
            elif self.current_screen == "profile":
                from nicegui_screens.profile_screen import ProfileScreen
                ProfileScreen(on_navigate=self._switch_screen)
            elif self.current_screen == "settings":
                SettingsScreen(on_navigate=self._switch_screen)
            elif self.current_screen == "students":
                def _on_issue_cert_handler(student_dict):
                    self._last_cert_student = student_dict
                    self._switch_screen("certificate")

                self._active_students_screen = StudentsScreen(on_issue_certificate=_on_issue_cert_handler)
                if getattr(self, "_pending_add_student", False):
                    self._pending_add_student = False
                    self._active_students_screen.form_view.render_add()
            elif self.current_screen == "orders":
                GraduationOrdersScreen()
            elif self.current_screen == "reports":
                from nicegui_screens.reports_screen import ReportsScreen
                ReportsScreen()
            elif self.current_screen == "courses":
                CoursesScreen()
            elif self.current_screen == "personnel":
                PersonnelScreen()
            elif self.current_screen == "certificate":
                def _on_edit_student_handler(student_dict):
                    self._last_cert_student = student_dict
                    self._switch_screen("students", defer=False)
                    if hasattr(self, "_active_students_screen") and self._active_students_screen:
                        def _back_to_cert(target_student=None):
                            st = target_student or student_dict
                            self._last_cert_student = st
                            self._switch_screen("certificate")
                        self._active_students_screen.profile_view.render(student_dict, from_cert=True, on_back_to_cert=_back_to_cert)

                last_st = getattr(self, "_last_cert_student", None)
                last_cert = getattr(self, "_last_cert_record", None)
                self._active_certificate_screen = CertificateScreen(
                    on_edit_student=_on_edit_student_handler,
                    initial_student=last_st,
                    initial_cert_record=last_cert
                )
                self._last_cert_record = None
            elif self.current_screen == "issued_certs":
                def _on_edit_issued_cert(cert_row):
                    sid = cert_row.get("student_id")
                    st = None
                    if sid:
                        try:
                            st = self.student_repo.get_by_id(int(sid))
                        except Exception as e:
                            log.warning(f"Error fetching student by id {sid}: {e}")
                    if not st:
                        st = {
                            "id": sid,
                            "student_name_ar": cert_row.get("student_name_ar"),
                            "student_name_en": cert_row.get("student_name_en"),
                        }
                    self._last_cert_student = st
                    self._last_cert_record = cert_row
                    self._switch_screen("certificate")

                IssuedCertificatesScreen(on_edit_certificate=_on_edit_issued_cert)
            else:
                self._build_placeholder_screen()
        log.info("[perf] screen %s built in %.0f ms", self.current_screen, (time.perf_counter() - t0) * 1000)

    # =========================================================================
    # 6. DASHBOARD CONTENT VIEW DEFINITION (CARDS, STATS, ACTIONS & TABLES)
    # =========================================================================
    def _build_dashboard_content(self) -> None:
        """
        [PAGE VIEW: DASHBOARD]
        1. Stats: Students, Issued certificates, Courses, Personnel (compact, one row when it fits)
        2. One large primary tile "إصدار كتاب" (+ a secondary "إضافة طالب")
        3. Recent students and recent issued certificates, side by side when wide
        """
        @ui.refreshable
        def stat_cards_section() -> None:
            with ui.element("div").classes("app-stat-grid"):
                for card_cfg in STAT_CARDS:
                    UI.stat_card(
                        title_ar=card_cfg["label_ar"],
                        value=self.counts.get(card_cfg["count_key"], 0),
                        icon_name=card_cfg["icon"],
                    )

        stat_cards_section()
        self._refresh_cards = stat_cards_section
        ui.timer(0.01, self._load_issued_count, once=True)

        # The one obvious next action
        with ui.row().classes("w-full gap-4 no-wrap items-stretch"):
            tile = ui.element("div").classes("app-cta-tile flex-1").props('tabindex="0" role="button"')
            tile.on("click", lambda: self._switch_screen("certificate"))
            tile.on("keydown.enter", lambda: self._switch_screen("certificate"))
            with tile:
                ui.icon("workspace_premium", size="32px")
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label("إصدار كتاب").classes("text-lg font-bold")
                    ui.label("اختر الطالب ثم نوع الوثيقة ثم أصدرها").classes("text-sm opacity-90")
                ui.icon("arrow_back", size="24px").classes("ms-auto")
            UI.secondary_button("إضافة طالب", icon="person_add", on_click=self._open_add_student).classes("self-center")

        # Recent records
        with ui.element("div").classes("app-two-col"):
            with UI.card("gap-2"):
                UI.page_header("أحدث الطلاب", actions=lambda: UI.ghost_button(
                    "عرض الكل", on_click=lambda: self._switch_screen("students")))
                rows_s = [
                    {
                        "id": s.get("id"),
                        "name": s.get("full_name_ar") or s.get("student_name_ar") or s.get("full_name_en") or "—",
                        "dept": s.get("dept_name_ar") or s.get("department_name_ar") or "—",
                        "grad": _fmt_grad_date(s.get("graduation_date")),
                        "raw_data": s,
                    }
                    for s in (self.recent_students or [])
                ]
                if rows_s:
                    s_table = UI.data_table(
                        [
                            {"name": "name", "label": "الاسم", "field": "name", "align": "right"},
                            {"name": "dept", "label": "القسم", "field": "dept"},
                            {"name": "grad", "label": "تاريخ التخرج", "field": "grad"},
                        ],
                        rows_s, clickable=True,
                    )
                    s_table.on("rowClick", lambda e: self._go_to_cert_for_student(e.args[1].get("raw_data") or e.args[1]))
                    with ui.row().classes("w-full"):
                        ui.label("انقر على طالب لإصدار كتاب له").classes("app-caption")
                else:
                    UI.empty_state("لا يوجد طلاب بعد", "أضف أول طالب من شاشة الطلاب.", icon="people")

            with UI.card("gap-2"):
                UI.page_header("أحدث الوثائق الصادرة", actions=lambda: UI.ghost_button(
                    "عرض الكل", on_click=lambda: self._switch_screen("issued_certs")))
                combined, seen = [], set()
                for c in (self.recent_certificates + getattr(self, "recent_printed_certificates", [])):
                    cid = c.get("id") or c.get("certificate_id")
                    if cid and cid not in seen:
                        seen.add(cid)
                        combined.append(c)
                rows_c = [
                    {
                        "id": c.get("id") or c.get("certificate_id"),
                        "name": c.get("full_name_ar") or c.get("student_name_ar") or c.get("student_name") or "—",
                        "number": c.get("certificate_number") or "—",
                        "date": str(c.get("issue_date") or c.get("created_at") or "—")[:10],
                        "raw_data": c,
                    }
                    for c in combined[:5]
                ]
                if rows_c:
                    c_table = UI.data_table(
                        [
                            {"name": "name", "label": "الطالب", "field": "name", "align": "right"},
                            {"name": "number", "label": "رقم الوثيقة", "field": "number"},
                            {"name": "date", "label": "تاريخ الإصدار", "field": "date"},
                        ],
                        rows_c, clickable=True,
                    )
                    c_table.on("rowClick", lambda e: self._go_to_cert_for_student(e.args[1].get("raw_data") or e.args[1]))
                    with ui.row().classes("w-full"):
                        ui.label("انقر على وثيقة لفتحها").classes("app-caption")
                else:
                    UI.empty_state("لم تصدر وثائق بعد", "ابدأ من «إصدار كتاب».", icon="description")

    def _open_add_student(self) -> None:
        """Add Student from anywhere: go to Students and open the add form."""
        self._pending_add_student = True
        self._switch_screen("students")

    def _go_to_cert_for_student(self, raw_student: dict) -> None:
        """Directs user to the Certificate Screen pre-loaded with the clicked student."""
        # Certificate dicts contain 'student_id', whereas student dicts have 'id'
        sid = raw_student.get("student_id") or raw_student.get("id")
        student_obj = None
        if sid:
            try:
                student_obj = self.student_repo.get_by_id(int(sid))
            except Exception as exc:
                log.warning(f"Failed to fetch student by id {sid}: {exc}")
        if not student_obj:
            student_obj = raw_student
            
        self._last_cert_student = student_obj
        if raw_student.get("certificate_number") or raw_student.get("template_type") or raw_student.get("certificate_id"):
            self._last_cert_record = raw_student
        else:
            self._last_cert_record = None
        self._switch_screen("certificate")

    # =========================================================================
    # 7. PLACEHOLDER VIEW DEFINITION
    # =========================================================================
    def _build_placeholder_screen(self) -> None:
        """
        [CARD / PAGE VIEW: PLACEHOLDER SCREEN]
        Fallback card for screens currently being migrated to NiceGUI:
        - Center Card Container (`UI.card()`)
        - Construction Icon (`ui.icon("construction")`)
        - Title & Subtitle Labels (`ui.label`)
        """
        header_ar, _ = self._get_screen_header_titles()
        with UI.card("items-center justify-center py-20"):
            ui.icon("construction", size="lg").classes("app-text-warning")
            ui.label(f"شاشة {header_ar} قيد التطوير").classes(
                "app-text-primary text-2xl font-bold"
            )

# Export MainAppShell as DashboardScreen for application entry point routing
DashboardScreen = MainAppShell
