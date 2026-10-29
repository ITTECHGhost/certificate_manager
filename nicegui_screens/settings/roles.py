# =============================================================================
# nicegui_screens/settings/roles.py — Settings: roles and permissions (RBAC)
# =============================================================================

import logging
from datetime import datetime
from nicegui import ui
from data.repositories import ALL_PERMISSION_KEYS
from nicegui_ui.ui_components import UI

log = logging.getLogger(__name__)


class RolesMixin:
    """Roles overview, full-page role editor and user permissions matrix (part of SettingsScreen)."""

    def _section_roles_and_permissions(self) -> None:
        """
        Renders the comprehensive Role-Based Access Control (RBAC) / Responsibility Management View.
        Uses full-page sub-view transitions (overview, edit_role, user_matrix) with NO popups!
        """
        @ui.refreshable
        def render_roles_container():
            if self.roles_subview_mode == "edit_role":
                self._render_full_page_role_editor()
            elif self.roles_subview_mode == "user_matrix":
                self._render_full_page_user_matrix()
            else:
                self._render_roles_overview()

        render_roles_container()
        self._render_roles_container = render_roles_container

    def _refresh_roles_section(self) -> None:
        """Refreshes the dynamic roles subview container."""
        if hasattr(self, '_render_roles_container') and self._render_roles_container:
            self._render_roles_container.refresh()

    def _open_role_editor_view(self, role_data=None) -> None:
        """Switches to the full-page Role Editor sub-view."""
        self.editing_role_data = role_data
        self.roles_subview_mode = "edit_role"
        self._refresh_roles_section()

    def _open_user_matrix_view(self, target_user_id=None) -> None:
        """Switches to the full-page User Permissions Matrix sub-view."""
        self.target_matrix_user_id = target_user_id
        self.roles_subview_mode = "user_matrix"
        self._refresh_roles_section()

    def _return_to_roles_overview(self) -> None:
        """Returns to the overview list of roles."""
        self.roles_subview_mode = "overview"
        self.editing_role_data = None
        self.target_matrix_user_id = None
        self._refresh_roles_section()

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 1: Roles Overview Grid
    # ─────────────────────────────────────────────────────────────────────────

    def _render_roles_overview(self) -> None:
        with UI.card().classes("w-full p-6 gap-6"):
            UI.card_header("إدارة الأدوار والمسؤوليات والصلاحيات — Roles & Permissions Matrix", "admin_panel_settings", icon_css="stat-text-emerald")

            # Header Banner & Action Buttons
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    with ui.element("div").classes("w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0"):
                        ui.icon("shield", size="md").classes("text-emerald-400")
                    with ui.column().classes("gap-0"):
                        ui.label("لوحة التحكم بالمسؤوليات والصلاحيات (RBAC Profiles)").classes("font-bold text-sm app-text-primary")
                        ui.label("تحديد المسؤوليات والأدوار في الكلية وضبط إمكانية الوصول إلى الشاشات والإجراءات والأقسام لكل دور.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2 flex-wrap"):
                    if self.on_navigate:
                        UI.secondary_button(
                            "شاشة الكوادر / Personnel Screen",
                            icon="group",
                            on_click=lambda: self.on_navigate("personnel")
                        ).classes("text-xs")

                    UI.secondary_button(
                        "تخصيص مستخدم / User Matrix",
                        icon="tune",
                        on_click=lambda: self._open_user_matrix_view()
                    ).classes("text-xs px-3 py-1.5")

                    UI.success_button(
                        "+ إضافة دور / مسؤولية جديدة",
                        icon="add_moderator",
                        on_click=lambda: self._open_role_editor_view(None)
                    ).classes("text-xs px-4 py-2 font-bold")

            # Roles Grid Display
            roles_list = []
            try:
                roles_list = self.role_repo.get_all() or []
            except Exception as e:
                log.warning(f"Failed to fetch roles: {e}")

            personnel_list = []
            try:
                personnel_list = self.p_repo.get_all() or []
            except Exception:
                pass

            page_names = {
                "home": "الرئيسية",
                "students": "الطلاب",
                "orders": "أوامر التخرج",
                "departments": "الأقسام",
                "courses": "المقررات",
                "personnel": "الكوادر",
                "certificate": "الوثائق",
                "issued_certs": "السجل",
                "settings": "الإعدادات",
                "history": "التغييرات"
            }

            all_perms_count = 29

            if not roles_list:
                with ui.column().classes("w-full items-center py-8 text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)]"):
                    ui.icon("shield_off", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أدوار مسجلة حالياً").classes("text-sm font-bold app-text-muted")
                return

            # Pre-compute personnel role mappings once to eliminate loop queries and HTTP hits
            personnel_role_map = {}
            for p in personnel_list:
                p_id = p.get("id")
                if p_id:
                    personnel_role_map[p_id] = self.role_repo.get_user_role_id(p_id, user_dict=p)

            with ui.grid(columns=2).classes("w-full gap-4 mt-2"):
                for role in roles_list:
                    role_id = role.get("id")
                    r_name_ar = role.get("name_ar") or role_id
                    r_name_en = role.get("name_en") or role_id
                    desc_ar = role.get("description_ar") or ""
                    allowed_pages = role.get("allowed_pages") or []
                    allowed_actions = role.get("allowed_actions") or []
                    dept_scope = role.get("department_scope") or "all"
                    is_sys = bool(role.get("is_system"))

                    matched_users = [
                        p for p in personnel_list
                        if (personnel_role_map.get(p.get("id")) == role_id or p.get("responsibility_ar") == r_name_ar or p.get("personnel_role") == role_id)
                    ]
                    user_count = len(matched_users)

                    with ui.column().classes(
                        "w-full p-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)] "
                        "hover:border-emerald-500/40 transition-all gap-3 shadow-sm"
                    ):
                        # Card Top Row: Name + Badges + Edit/Delete
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.row().classes("items-center gap-2.5 min-w-0 flex-1"):
                                with ui.element("div").classes("w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0"):
                                    ui.icon("verified_user" if is_sys else "shield", size="sm").classes("text-blue-400")
                                with ui.column().classes("gap-0 min-w-0 flex-1"):
                                    with ui.row().classes("items-center gap-2 flex-wrap"):
                                        ui.label(r_name_ar).classes("text-sm font-bold app-text-primary")
                                        if is_sys:
                                            ui.label("افتراضي / Built-in").classes("text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 font-semibold border border-blue-500/30")
                                        else:
                                            ui.label("مخصص / Custom").classes("text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-semibold border border-emerald-500/30")
                                    ui.label(r_name_en).classes("text-xs app-text-muted font-mono")

                            with ui.row().classes("items-center gap-1 shrink-0"):
                                ui.button(
                                    icon="edit",
                                    on_click=lambda r=role: self._open_role_editor_view(r)
                                ).props("flat round dense size=sm color=primary").tooltip("تعديل هذا الدور والصلاحيات / Edit Role (Full Page)")

                                if not is_sys:
                                    def _confirm_delete_role(rid=role_id, rname=r_name_ar):
                                        del_dlg = ui.dialog()
                                        with del_dlg, UI.card().classes("p-6 gap-4 w-96 rounded-2xl bg-[var(--surface-card)] border border-[var(--border-default)] shadow-2xl"):
                                            ui.label("تأكيد حذف الدور — Confirm Delete").classes("text-base font-bold text-red-400")
                                            ui.label(f"هل أنت متأكد من حذف الدور المخصص ({rname}) نهائياً؟").classes("text-xs app-text-muted leading-relaxed")
                                            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                                                UI.ghost_button("إلغاء / Cancel", on_click=del_dlg.close).classes("text-xs")
                                                def _do_del():
                                                    try:
                                                        self.role_repo.delete_role(rid)
                                                        ui.notify(f"تم حذف الدور ({rname}) بنجاح", type="positive")
                                                        del_dlg.close()
                                                        self._refresh_roles_section()
                                                    except Exception as exc:
                                                        ui.notify(f"خطأ أثناء حذف الدور: {exc}", type="negative")
                                                UI.danger_button("تأكيد الحذف", icon="delete", on_click=_do_del).classes("text-xs")
                                        del_dlg.open()

                                    ui.button(
                                        icon="delete",
                                        on_click=_confirm_delete_role
                                    ).props("flat round dense size=sm color=negative").tooltip("حذف هذا الدور المخصص / Delete Role")

                        if desc_ar:
                            ui.label(desc_ar).classes("text-xs app-text-muted leading-relaxed")

                        # Details Stats & Badges Grid
                        with ui.column().classes("w-full gap-2 pt-2 border-t border-[var(--border-default)]"):
                            # 1. Allowed Pages Badges
                            with ui.row().classes("w-full items-center gap-1.5 flex-wrap"):
                                ui.label("الشاشات:").classes("text-[11px] font-bold app-text-muted shrink-0")
                                if len(allowed_pages) >= 9:
                                    ui.label("كافة الشاشات (Full Page Access)").classes("text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold")
                                elif not allowed_pages:
                                    ui.label("لا توجد شاشات").classes("text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400")
                                else:
                                    for pkey in allowed_pages[:5]:
                                        ui.label(page_names.get(pkey, pkey)).classes("text-[10px] px-2 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border-default)] app-text-primary")
                                    if len(allowed_pages) > 5:
                                        ui.label(f"+{len(allowed_pages)-5} أخرى").classes("text-[10px] px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-400")

                            # 2. Allowed Permissions & Departments Row
                            with ui.row().classes("w-full items-center justify-between text-xs pt-1"):
                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("check_circle", size="xs").classes("text-emerald-400")
                                    ui.label(f"الصلاحيات: {len(allowed_actions)} من {all_perms_count}").classes("font-semibold app-text-primary text-[11px]")

                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("domain", size="xs").classes("text-purple-400")
                                    dept_label = "كافة الأقسام" if (dept_scope == "all" or not dept_scope) else "أقسام مخصصة"
                                    ui.label(f"الأقسام: {dept_label}").classes("font-semibold app-text-muted text-[11px]")

                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("people", size="xs").classes("text-blue-400")
                                    ui.label(f"الكوادر: {user_count}").classes("font-semibold app-text-muted text-[11px]")

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 2: Dedicated Full-Page Role Editor (NO POPUP MODAL)
    # ─────────────────────────────────────────────────────────────────────────

    def _render_full_page_role_editor(self) -> None:
        import json
        is_edit = self.editing_role_data is not None
        initial_data = self.editing_role_data or {}
        r_id = initial_data.get("id") or ""
        is_sys = bool(initial_data.get("is_system", 0))

        all_perms = []
        try:
            all_perms = self.perm_repo.get_all() or []
        except Exception:
            pass

        all_depts = []
        try:
            all_depts = self.dept_repo.get_all() or []
        except Exception:
            pass

        with UI.card().classes("w-full p-6 gap-6"):
            # Sticky/Prominent Top Navigation Bar
            with ui.row().classes("w-full items-center justify-between pb-4 border-b border-[var(--border-default)] shrink-0 gap-4 flex-wrap"):
                with ui.row().classes("items-center gap-3"):
                    UI.secondary_button(
                        "← العودة لقائمة الأدوار / Back to Roles",
                        icon="arrow_forward",
                        on_click=self._return_to_roles_overview
                    ).classes("text-xs px-4 py-2 font-bold shadow-sm")

                    with ui.element("div").classes("w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center"):
                        ui.icon("admin_panel_settings", size="sm").classes("text-blue-400")

                    with ui.column().classes("gap-0"):
                        title_lbl = f"تعديل الدور: {initial_data.get('name_ar', '')}" if is_edit else "إنشاء دور / مسؤولية جديدة — Create Role Profile"
                        ui.label(title_lbl).classes("text-base font-bold app-text-primary")
                        ui.label("تحديد صلاحيات الوصول إلى الشاشات والإجراءات والأقسام لهذا الدور بالتفصيل.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    UI.ghost_button("إلغاء / Cancel", on_click=self._return_to_roles_overview).classes("text-xs px-3 py-2")
                    save_btn_top = UI.success_button(
                        "حفظ الدور والصلاحيات / Save Role",
                        icon="check_circle",
                        on_click=lambda: _save_role()
                    ).classes("text-xs px-5 py-2 font-bold shadow-md")

            # Form Body: Full-Width Structured Cards
            with ui.column().classes("w-full gap-6"):

                # ── 1. Basic Role Information ─────────────────────────────────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("badge", size="sm").classes("text-blue-400")
                        ui.label("المعلومات الأساسية للدور — Role Details").classes("text-sm font-bold text-blue-400")

                    with ui.grid(columns=2).classes("w-full gap-4"):
                        name_ar_input = UI.text_input("اسم الدور / المسؤولية (بالعربية) *", value=initial_data.get("name_ar", ""))
                        name_en_input = UI.text_input("اسم الدور / المسؤولية (بالإنكليزية) *", value=initial_data.get("name_en", ""))

                    desc_ar_input = UI.text_input("وصف الدور والمهام / Description", value=initial_data.get("description_ar", "")).classes("w-full")

                # ── 2. Department Accessibility Scope (Granular Catalog Access) ─
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("domain", size="sm").classes("text-amber-400")
                            ui.label("نطاق الأقسام المسموح بالوصول إليها — Department Accessibility Scope").classes("text-sm font-bold text-amber-400")
                        ui.label("تحكم بالأقسام التي يستطيع هذا الدور الاطلاع على طلبتها ومقرراتها").classes("text-xs app-text-muted")

                    init_scope = initial_data.get("department_scope") or "all"
                    is_all_depts = (init_scope == "all" or not init_scope)

                    dept_radio = ui.radio(
                        {"all": "كافة الأقسام العلمية (All Departments)", "specific": "أقسام محددة فقط (Specific Departments Only)"},
                        value="all" if is_all_depts else "specific"
                    ).props("inline dense").classes("text-xs font-bold app-text-primary")

                    dept_checkboxes = {}
                    dept_boxes_wrapper = ui.column().classes("w-full gap-3 pt-2")
                    with dept_boxes_wrapper:
                        parsed_scope = []
                        if not is_all_depts and isinstance(init_scope, str):
                            try:
                                parsed_scope = json.loads(init_scope)
                            except Exception:
                                parsed_scope = [int(x) for x in init_scope.split(",") if x.strip().isdigit()]
                        elif isinstance(init_scope, list):
                            parsed_scope = init_scope

                        with ui.row().classes("w-full justify-between items-center pb-1 border-b border-[var(--border-default)]"):
                            ui.label("حدد الأقسام المتاحة لهذا الدور:").classes("text-xs font-bold app-text-primary")
                            with ui.row().classes("gap-2"):
                                def _sel_all_depts():
                                    for dcb in dept_checkboxes.values():
                                        dcb.value = True
                                def _clr_all_depts():
                                    for dcb in dept_checkboxes.values():
                                        dcb.value = False
                                UI.ghost_button("تحديد كافة الأقسام", icon="select_all", on_click=_sel_all_depts).classes("text-xs px-2 py-1")
                                UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clr_all_depts).classes("text-xs px-2 py-1")

                        with ui.grid(columns=3).classes("w-full gap-3"):
                            for d in all_depts:
                                did = d["id"]
                                dname = d.get("name_ar") or d.get("name_en") or f"قسم {did}"
                                dcode = d.get("code") or ""
                                label_text = f"{dname} ({dcode})" if dcode else dname
                                dcb = ui.checkbox(label_text, value=(did in parsed_scope or str(did) in parsed_scope)).classes("text-xs")
                                dept_checkboxes[did] = dcb

                    def _on_scope_toggle(val):
                        v = val.value if hasattr(val, "value") else val
                        dept_boxes_wrapper.set_visibility(v == "specific")

                    dept_radio.on_value_change(_on_scope_toggle)
                    dept_boxes_wrapper.set_visibility(not is_all_depts)

                # ── 3. Page Accessibility ─────────────────────────────────────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("layers", size="sm").classes("text-purple-400")
                            ui.label("الشاشات والصفحات المتاح الوصول إليها — Accessible Pages").classes("text-sm font-bold text-purple-400")
                        with ui.row().classes("gap-2"):
                            def _select_all_pages():
                                for cb in page_checkboxes.values():
                                    cb.value = True
                            def _clear_all_pages():
                                for cb in page_checkboxes.values():
                                    cb.value = False
                            UI.ghost_button("تحديد كافة الشاشات", icon="select_all", on_click=_select_all_pages).classes("text-xs px-2.5 py-1")
                            UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clear_all_pages).classes("text-xs px-2.5 py-1")

                    all_pages_map = {
                        "home": ("الرئيسية / Dashboard", "home"),
                        "students": ("إدارة الطلاب والدرجات / Students", "school"),
                        "orders": ("أوامر التخرج / Orders", "history_edu"),
                        "departments": ("إدارة الأقسام / Departments", "domain"),
                        "courses": ("المواد الدراسية / Courses", "menu_book"),
                        "personnel": ("إدارة الكوادر / Personnel", "group"),
                        "certificate": ("إصدار الوثيقة / Certificates", "print"),
                        "issued_certs": ("سجل الوثائق الصادرة / Log", "list_alt"),
                        "settings": ("إعدادات النظام / Settings", "settings"),
                        "history": ("سجل النشاط والتغييرات / History", "history"),
                    }

                    current_pages = set(initial_data.get("allowed_pages") or [])
                    if not is_edit and not current_pages:
                        current_pages = {"home", "students", "orders", "certificate", "issued_certs"}

                    page_checkboxes = {}
                    with ui.grid(columns=3).classes("w-full gap-3"):
                        for p_key, (p_title, p_icon) in all_pages_map.items():
                            with ui.row().classes("items-center justify-between p-3 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] hover:border-purple-500/30 transition-all"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon(p_icon, size="xs").classes("text-purple-400")
                                    ui.label(p_title).classes("text-xs font-semibold app-text-primary")
                                cb = ui.checkbox(value=(p_key in current_pages))
                                page_checkboxes[p_key] = cb

                # ── 4. Granular Action Permissions (The Complete Catalog) ─────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("verified_user", size="sm").classes("text-emerald-400")
                            ui.label("صلاحيات الإجراءات والعمليات المفصلة — Granular Action Permissions").classes("text-sm font-bold text-emerald-400")
                        with ui.row().classes("gap-2"):
                            def _grant_all_acts():
                                for sw in action_switches.values():
                                    sw.value = True
                            def _clear_all_acts():
                                for sw in action_switches.values():
                                    sw.value = False
                            UI.ghost_button("تحديد كافة الصلاحيات", icon="select_all", on_click=_grant_all_acts).classes("text-xs px-2.5 py-1")
                            UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clear_all_acts).classes("text-xs px-2.5 py-1")

                    # 8 Distinct, Comprehensive Categories
                    categories = {
                        "students": {
                            "title": "🎓 شؤون الطلاب والدرجات — Students & Grades",
                            "color": "text-blue-400",
                            "desc": "صلاحيات الاطلاع والإضافة والتعديل والحذف وإدارة درجات الطلبة"
                        },
                        "orders": {
                            "title": "📜 أوامر التخرج — Graduation Orders",
                            "color": "text-purple-400",
                            "desc": "صلاحيات استعراض وإنشاء وتعديل وحذف أوامر التخرج وربط الطلبة"
                        },
                        "certificates": {
                            "title": "🖨️ إصدار الوثائق الرسمية — Issue Certificates",
                            "color": "text-emerald-400",
                            "desc": "صلاحية توليد وتعيين أرقام وثائق التخرج الرسمية وطباعتها"
                        },
                        "issued_certs": {
                            "title": "📋 سجل الوثائق الصادرة — Issued Records & Logs",
                            "color": "text-teal-400",
                            "desc": "صلاحيات البحث في الأرشيف وتصدير السجلات وحذف القيود الصادرة"
                        },
                        "departments": {
                            "title": "🏢 إدارة الأقسام العلمية — Departments Management",
                            "color": "text-amber-400",
                            "desc": "صلاحيات استعراض وإضافة وتعديل وحذف الأقسام العلمية والتخصصات"
                        },
                        "courses": {
                            "title": "📚 المقررات والمناهج الدراسية — Courses Catalog",
                            "color": "text-indigo-400",
                            "desc": "صلاحيات عرض وإضافة وتعديل وحذف المواد الدراسية وتعيين ساعاتها ووحداتها"
                        },
                        "personnel": {
                            "title": "👥 الكوادر والمستخدمين — Personnel & Accounts",
                            "color": "text-orange-400",
                            "desc": "صلاحيات عرض ملفات الكوادر وإدارة الحسابات وتعيين الأدوار"
                        },
                        "settings": {
                            "title": "⚙️ إعدادات النظام — System Settings Views & Alter",
                            "color": "text-cyan-400",
                            "desc": "صلاحيات الوصول وتعديل كل شاشة من شاشات إعدادات النظام بشكل منفصل"
                        },
                    }

                    action_switches = {}
                    current_actions = set(initial_data.get("allowed_actions") or [])

                    # Backward compatibility mapping for legacy catalog:manage ONLY if no granular permissions exist
                    has_granular_catalog = any(k.startswith("departments:") or k.startswith("courses:") for k in current_actions)
                    if "catalog:manage" in current_actions and not has_granular_catalog:
                        for k in ["departments:view", "departments:create", "departments:edit", "departments:delete",
                                  "courses:view", "courses:create", "courses:edit", "courses:delete"]:
                            current_actions.add(k)

                    has_granular_settings = any(k.startswith("settings:") and k not in ("settings:manage", "settings:view") for k in current_actions)
                    if "settings:manage" in current_actions and not has_granular_settings:
                        for k in ["settings:institution", "settings:study_systems", "settings:appearance",
                                  "settings:templates", "settings:logs"]:
                            current_actions.add(k)

                    with ui.column().classes("w-full gap-5 pt-1"):
                        for cat_key, cat_meta in categories.items():
                            cat_perms = [p for p in all_perms if p.get("category") == cat_key and p.get("permission_key") in ALL_PERMISSION_KEYS]
                            if not cat_perms:
                                continue

                            with ui.column().classes("w-full p-4 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] gap-3"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(cat_meta["title"]).classes(f"font-bold text-xs {cat_meta['color']}")
                                        ui.label(cat_meta["desc"]).classes("text-[10px] app-text-muted")

                                    # Category quick select/clear
                                    def _make_cat_toggles(cp_list=cat_perms):
                                        def _sel():
                                            for p in cp_list:
                                                if p["permission_key"] in action_switches:
                                                    action_switches[p["permission_key"]].value = True
                                        def _clr():
                                            for p in cp_list:
                                                if p["permission_key"] in action_switches:
                                                    action_switches[p["permission_key"]].value = False
                                        return _sel, _clr

                                    sel_fn, clr_fn = _make_cat_toggles(cat_perms)
                                    with ui.row().classes("gap-1"):
                                        UI.ghost_button("الكل", icon="done_all", on_click=sel_fn).classes("text-[10px] px-1.5 py-0.5")
                                        UI.ghost_button("مسح", icon="remove_done", on_click=clr_fn).classes("text-[10px] px-1.5 py-0.5")

                                with ui.grid(columns=2).classes("w-full gap-3 pt-1"):
                                    for perm in cat_perms:
                                        pkey = perm["permission_key"]
                                        pname_ar = perm.get("name_ar") or pkey
                                        pname_en = perm.get("name_en") or pkey
                                        pdesc = perm.get("description_ar") or ""

                                        with ui.row().classes("items-center justify-between p-2.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-main)] hover:border-emerald-500/30 transition-all"):
                                            with ui.column().classes("gap-0 min-w-0 flex-1"):
                                                ui.label(f"{pname_ar} / {pname_en}").classes("text-xs font-bold app-text-primary truncate")
                                                if pdesc:
                                                    ui.label(pdesc).classes("text-[10px] app-text-muted line-clamp-1")
                                            sw = ui.switch(value=(pkey in current_actions)).props("dense size=sm color=positive")
                                            action_switches[pkey] = sw

            # Sticky / Bottom Action Bar
            with ui.row().classes("w-full items-center justify-between pt-6 border-t border-[var(--border-default)] mt-4"):
                UI.secondary_button("← إلغاء والعودة لقائمة الأدوار", on_click=self._return_to_roles_overview).classes("text-xs px-4 py-2")

                def _save_role():
                    nar = (name_ar_input.value or "").strip()
                    nen = (name_en_input.value or "").strip()
                    if not nar:
                        ui.notify("يرجى إدخال اسم الدور / المسؤولية بالعربية!", type="warning")
                        return
                    if not nen:
                        nen = nar

                    sel_pages = [pk for pk, cb in page_checkboxes.items() if cb.value]
                    sel_actions = [ak for ak, sw in action_switches.items() if sw.value and ak in ALL_PERMISSION_KEYS]

                    scope_val = "all"
                    if dept_radio.value == "specific":
                        chosen_depts = [did for did, dcb in dept_checkboxes.items() if dcb.value]
                        scope_val = json.dumps(chosen_depts) if chosen_depts else "all"

                    # Determine assigned slug ID
                    assigned_id = r_id
                    if not assigned_id:
                        import re
                        slug_base = re.sub(r'[^a-zA-Z0-9_]', '_', nen.strip().lower()).strip('_')
                        if not slug_base:
                            slug_base = f"role_{int(datetime.now().timestamp()) % 100000}"
                        # Check collision if adding a new role
                        existing = self.role_repo.get_by_id(slug_base)
                        if existing:
                            slug_base = f"{slug_base}_{int(datetime.now().timestamp()) % 10000}"
                        assigned_id = slug_base

                    existing_base = initial_data.get("base_role") if is_edit else None
                    base_role_val = existing_base or ("admin" if assigned_id == "admin" else "user")

                    payload = {
                        "id": assigned_id,
                        "name_ar": nar,
                        "name_en": nen,
                        "description_ar": (desc_ar_input.value or "").strip(),
                        "base_role": base_role_val,
                        "allowed_pages": sel_pages,
                        "allowed_actions": sel_actions,
                        "department_scope": scope_val,
                        "is_system": 1 if is_sys else 0
                    }

                    try:
                        self.role_repo.save_role(payload)
                        self.session.refresh_access()  # the edited role may be the logged-in user's
                        ui.notify(f"تم حفظ الدور ({nar}) بنجاح!", type="positive")
                        self._return_to_roles_overview()
                    except Exception as exc:
                        ui.notify(f"خطأ أثناء حفظ الدور: {exc}", type="negative")

                UI.success_button(
                    "حفظ الدور والصلاحيات / Save Role Profile",
                    icon="check_circle",
                    on_click=_save_role
                ).classes("text-xs px-6 py-2.5 font-bold shadow-md")

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 3: Dedicated Full-Page User Permissions Matrix (NO POPUP MODAL)
    # ─────────────────────────────────────────────────────────────────────────

    def _render_full_page_user_matrix(self) -> None:
        all_perms = []
        try:
            all_perms = self.perm_repo.get_all() or []
        except Exception as e:
            log.warning(f"Failed to fetch permissions catalog: {e}")

        personnel_list = []
        try:
            personnel_list = self.p_repo.get_all() or []
        except Exception as e:
            log.warning(f"Failed to fetch personnel for matrix: {e}")

        if not personnel_list:
            with UI.card().classes("w-full p-6 gap-4"):
                ui.label("لا توجد حسابات كوادر مسجلة! / No personnel accounts found").classes("text-sm text-red-400 font-bold")
                UI.secondary_button("← العودة لقائمة الأدوار", on_click=self._return_to_roles_overview)
            return

        initial_id = self.target_matrix_user_id or self.emp_id
        if not any(p.get("id") == initial_id for p in personnel_list):
            initial_id = personnel_list[0].get("id")

        with UI.card().classes("w-full p-6 gap-6"):
            # Header Navigation Bar
            with ui.row().classes("w-full items-center justify-between pb-4 border-b border-[var(--border-default)] shrink-0 gap-4 flex-wrap"):
                with ui.row().classes("items-center gap-3"):
                    UI.secondary_button(
                        "← العودة لقائمة الأدوار / Back to Roles",
                        icon="arrow_forward",
                        on_click=self._return_to_roles_overview
                    ).classes("text-xs px-4 py-2 font-bold shadow-sm")

                    with ui.element("div").classes("w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center"):
                        ui.icon("shield", size="sm").classes("text-emerald-400")

                    with ui.column().classes("gap-0"):
                        ui.label("لوحة التحكم بصلاحيات المستخدمين — User Permissions Matrix").classes("text-base font-bold app-text-primary")
                        ui.label("تخصيص الصلاحيات الفردية الممنوحة لكل حساب كادر في النظام بشكل مباشر ومفصل.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    UI.ghost_button("إلغاء / Cancel", on_click=self._return_to_roles_overview).classes("text-xs px-3 py-2")
                    save_btn_top = UI.success_button(
                        "حفظ الصلاحيات / Save Permissions",
                        icon="check_circle",
                        on_click=lambda: _save_user_permissions()
                    ).classes("text-xs px-5 py-2 font-bold shadow-md")

            user_options = {
                p["id"]: f"{p.get('name_ar', '')} (@{p.get('username', '')}) — [{p.get('personnel_role', 'user')}]"
                for p in personnel_list
            }

            all_pages_map = {
                "home": ("الرئيسية / Dashboard", "home"),
                "students": ("إدارة الطلاب والدرجات / Students", "school"),
                "orders": ("أوامر التخرج / Orders", "history_edu"),
                "departments": ("إدارة الأقسام / Departments", "domain"),
                "courses": ("المواد الدراسية / Courses", "menu_book"),
                "personnel": ("إدارة الكوادر / Personnel", "group"),
                "certificate": ("إصدار الوثيقة / Certificates", "print"),
                "issued_certs": ("سجل الوثائق الصادرة / Log", "list_alt"),
                "settings": ("إعدادات النظام / Settings", "settings"),
                "history": ("سجل النشاط والتغييرات / History", "history"),
            }

            state = {
                "selected_user_id": initial_id,
                "switches": {},
                "page_checkboxes": {},
                "granted_keys": set()
            }

            def load_user_perms(uid):
                state["selected_user_id"] = uid
                try:
                    granted = set(self.perm_repo.get_user_permissions(uid) or [])
                except Exception:
                    granted = set()
                state["granted_keys"] = granted

                # Action switches
                for k, sw in state["switches"].items():
                    sw.value = (k in granted)

                # Page accessibility checkboxes
                user_pages = {k.replace("page:", "") for k in granted if k.startswith("page:")}
                if not user_pages:
                    # Inherit from assigned role
                    user_rec = next((p for p in personnel_list if p.get("id") == uid), None)
                    if user_rec:
                        r_key = user_rec.get("personnel_role") or "user"
                        role_rec = self.role_repo.get_by_id(r_key)
                        if role_rec and role_rec.get("allowed_pages"):
                            user_pages = set(role_rec.get("allowed_pages"))
                        elif r_key == "admin":
                            user_pages = set(all_pages_map.keys())
                        else:
                            user_pages = {"home", "students", "orders", "certificate", "issued_certs"}
                    else:
                        user_pages = {"home", "students", "orders", "certificate", "issued_certs"}

                for pkey, cb in state["page_checkboxes"].items():
                    cb.value = (pkey in user_pages)

            # Controls Toolbar: User Selection & Quick Presets
            with ui.row().classes("w-full items-center justify-between gap-3 p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap"):
                with ui.row().classes("items-center gap-2 flex-1 min-w-[320px]"):
                    ui.label("المستخدم المحدد / User:").classes("text-xs font-bold app-text-primary shrink-0")
                    user_select = UI.select(
                        "",
                        options=user_options,
                        value=initial_id,
                        on_change=lambda e: load_user_perms(e.value)
                    ).classes("flex-1 text-xs")

                with ui.row().classes("items-center gap-2 flex-wrap shrink-0"):
                    def _grant_all():
                        for k, sw in state["switches"].items():
                            sw.value = True
                        for cb in state["page_checkboxes"].values():
                            cb.value = True
                        ui.notify("تم تحديد جميع الصلاحيات والشاشات", type="info")

                    def _revoke_all():
                        for k, sw in state["switches"].items():
                            sw.value = False
                        for cb in state["page_checkboxes"].values():
                            cb.value = False
                        ui.notify("تم إلغاء جميع الصلاحيات والشاشات", type="info")

                    def _default_user():
                        default_keys = {
                            "students:view", "orders:view", "certificates:issue",
                            "issued_certs:view", "departments:view", "courses:view", "personnel:view"
                        }
                        for k, sw in state["switches"].items():
                            sw.value = (k in default_keys)
                        def_pages = {"home", "students", "orders", "certificate", "issued_certs"}
                        for pkey, cb in state["page_checkboxes"].items():
                            cb.value = (pkey in def_pages)
                        ui.notify("تم تطبيق النمط الافتراضي للمستخدم", type="info")

                    def _registrar_preset():
                        reg_keys = {
                            "students:view", "students:create", "students:edit", "students:grades",
                            "orders:view", "orders:create", "orders:edit",
                            "certificates:issue", "issued_certs:view", "issued_certs:export",
                            "departments:view", "courses:view"
                        }
                        for k, sw in state["switches"].items():
                            sw.value = (k in reg_keys)
                        reg_pages = {"home", "students", "orders", "departments", "courses", "certificate", "issued_certs"}
                        for pkey, cb in state["page_checkboxes"].items():
                            cb.value = (pkey in reg_pages)
                        ui.notify("تم تطبيق نمط شؤون الطلاب والتسجيل", type="info")

                    UI.ghost_button("تحديد الكل", icon="select_all", on_click=_grant_all).classes("text-xs px-2.5 py-1.5")
                    UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_revoke_all).classes("text-xs px-2.5 py-1.5")
                    UI.secondary_button("نمط مستخدم", icon="tune", on_click=_default_user).classes("text-xs px-2.5 py-1.5")
                    UI.secondary_button("نمط تسجيل", icon="school", on_click=_registrar_preset).classes("text-xs px-2.5 py-1.5")

            # ── Accessible Pages for User Card ───────────────────────────────
            with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                with ui.row().classes("w-full items-center justify-between pb-2 border-b border-[var(--border-default)]"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("layers", size="sm").classes("text-purple-400")
                        ui.label("الشاشات والصفحات المتاح الوصول إليها للمستخدم — Accessible Pages").classes("text-sm font-bold text-purple-400")
                    with ui.row().classes("gap-2"):
                        def _sel_all_p():
                            for cb in state["page_checkboxes"].values():
                                cb.value = True
                        def _clr_all_p():
                            for cb in state["page_checkboxes"].values():
                                cb.value = False
                        UI.ghost_button("تحديد كافة الشاشات", icon="select_all", on_click=_sel_all_p).classes("text-xs px-2.5 py-1")
                        UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clr_all_p).classes("text-xs px-2.5 py-1")

                with ui.grid(columns=3).classes("w-full gap-3"):
                    for p_key, (p_title, p_icon) in all_pages_map.items():
                        with ui.row().classes("items-center justify-between p-3 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] hover:border-purple-500/30 transition-all"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon(p_icon, size="xs").classes("text-purple-400")
                                ui.label(p_title).classes("text-xs font-semibold app-text-primary")
                            cb = ui.checkbox(value=False)
                            state["page_checkboxes"][p_key] = cb

            # 8 Categories Cards
            categories = {
                "students": {"title": "🎓 شؤون الطلاب والدرجات — Students & Grades", "color": "text-blue-400"},
                "orders": {"title": "📜 أوامر التخرج — Graduation Orders", "color": "text-purple-400"},
                "certificates": {"title": "🖨️ إصدار الوثائق الرسمية — Issue Certificates", "color": "text-emerald-400"},
                "issued_certs": {"title": "📋 سجل الوثائق الصادرة — Issued Records & Logs", "color": "text-teal-400"},
                "departments": {"title": "🏢 إدارة الأقسام العلمية — Departments Management", "color": "text-amber-400"},
                "courses": {"title": "📚 المقررات والمناهج الدراسية — Courses Catalog", "color": "text-indigo-400"},
                "personnel": {"title": "👥 الكوادر والمستخدمين — Personnel & Accounts", "color": "text-orange-400"},
                "settings": {"title": "⚙️ إعدادات النظام — System Settings Views & Alter", "color": "text-cyan-400"},
            }

            with ui.column().classes("w-full gap-5"):
                for cat_key, cat_meta in categories.items():
                    cat_perms = [p for p in all_perms if p.get("category") == cat_key and p.get("permission_key") in ALL_PERMISSION_KEYS]
                    if not cat_perms:
                        continue

                    with ui.column().classes("w-full p-4 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] gap-3"):
                        ui.label(cat_meta["title"]).classes(f"font-bold text-xs {cat_meta['color']}")

                        with ui.grid(columns=2).classes("w-full gap-3"):
                            for perm in cat_perms:
                                pkey = perm["permission_key"]
                                pname_ar = perm.get("name_ar") or pkey
                                pname_en = perm.get("name_en") or pkey
                                pdesc = perm.get("description_ar") or ""

                                with ui.row().classes("items-center justify-between p-2.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-main)] hover:border-emerald-500/30 transition-all"):
                                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                                        ui.label(f"{pname_ar} / {pname_en}").classes("text-xs font-bold app-text-primary truncate")
                                        if pdesc:
                                             ui.label(pdesc).classes("text-[10px] app-text-muted truncate")
                                    sw = ui.switch().props("dense size=sm color=positive")
                                    state["switches"][pkey] = sw

            load_user_perms(initial_id)

            # Bottom Actions Bar
            with ui.row().classes("w-full items-center justify-between pt-6 border-t border-[var(--border-default)] mt-4"):
                UI.secondary_button("← إلغاء والعودة لقائمة الأدوار", on_click=self._return_to_roles_overview).classes("text-xs px-4 py-2")

                def _save_user_permissions():
                    try:
                        uid = state["selected_user_id"]
                        granted_actions = [k for k, sw in state["switches"].items() if sw.value and k in ALL_PERMISSION_KEYS]
                        granted_pages = [f"page:{p_key}" for p_key, cb in state["page_checkboxes"].items() if cb.value]
                        all_to_save = granted_actions + granted_pages
                        self.perm_repo.set_user_permissions(uid, all_to_save)
                        self.session.refresh_access(uid)
                        ui.notify(
                            f"تم حفظ الصلاحيات والشاشات للمستخدم بنجاح! ({len(granted_actions)} إجراء + {len(granted_pages)} شاشة)",
                            type="positive"
                        )
                    except Exception as err:
                        ui.notify(f"خطأ أثناء حفظ الصلاحيات: {err}", type="negative")

                UI.success_button(
                    "حفظ صلاحيات وشاشات المستخدم / Save Permissions",
                    icon="check_circle",
                    on_click=_save_user_permissions
                ).classes("text-xs px-6 py-2.5 font-bold shadow-md")
