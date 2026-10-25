import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import PersonnelRepository, RoleRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)

# display_order is the ONLY signatory column in MySQL.
# 0 = not a signatory.  1-10 = signatory with that position number.
ORDER_OPTIONS = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "بدون / None": 0,
}

class PersonnelScreen:
    """
    Personnel Management Screen (NiceGUI version).
    Uses full page views for list and edit modes (view replacing UI).
    """

    def __init__(self):
        self.repo = PersonnelRepository()
        self.role_repo = RoleRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""

        self.container = ui.column().classes("w-full h-full p-6 gap-6")
        self.show_list_view()

    def show_list_view(self):
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col w-full h-full"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("manage_accounts", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إدارة الكوادر والمستخدمين — Personnel").classes("text-xl font-bold app-text-primary")
                            ui.label("إدارة مستخدمي النظام والموقعين على الوثائق").classes("text-xs app-text-muted")

                    UI.success_button(
                        "+ إضافة كادر / Add Personnel",
                        icon="person_add",
                        on_click=lambda: self.show_edit_view(mode="add")
                    ).classes("text-sm px-5 py-2.5 shrink-0")

                # Controls Row
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap shrink-0"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-[300px]"):
                        def on_search_change(e):
                            val = extract_event_value(e, default="")
                            self.search_term = str(val or "").strip().lower()
                            self.current_offset = 0
                            self._render_content()

                        UI.text_input(
                            label="",
                            placeholder="بحث بالاسم أو اسم المستخدم... / Search by name or username...",
                            on_change=on_search_change
                        ).classes("flex-1 text-sm")

                    with ui.row().classes("items-center gap-2 shrink-0"):
                        ui.label("عرض / Show:").classes("text-xs font-bold app-text-muted")

                        def on_limit_change(e):
                            val = extract_event_value(e, default=25)
                            try:
                                self.current_limit = int(val or 25)
                            except Exception:
                                self.current_limit = 25
                            self.current_offset = 0
                            self._render_content()

                        UI.select(
                            label="",
                            options={25: "25", 50: "50", 75: "75", 100: "100"},
                            value=self.current_limit,
                            on_change=on_limit_change
                        ).classes("w-24 text-sm")

                @ui.refreshable
                def content_view():
                    self._build_table()

                content_view()
                self._refresh_content = content_view

    def _render_content(self):
        if hasattr(self, "_refresh_content"):
            self._refresh_content.refresh()

    def _get_filtered_data(self) -> list[dict]:
        try:
            rows = self.repo.get_all() or []
        except Exception as err:
            log.warning(f"Failed to fetch personnel: {err}")
            return []

        if not self.search_term:
            return rows

        t = self.search_term
        filtered = [
            r for r in rows
            if t in str(r.get("name_ar") or "").lower()
            or t in str(r.get("name_en") or "").lower()
            or t in str(r.get("username") or "").lower()
            or t in str(r.get("academic_title_ar") or "").lower()
            or t in str(r.get("responsibility_ar") or "").lower()
        ]
        return filtered

    def _build_table(self):
        all_rows = self._get_filtered_data()
        total_count = len(all_rows)
        
        start_idx = self.current_offset
        end_idx = start_idx + self.current_limit
        page_rows = all_rows[start_idx:end_idx]

        with ui.column().classes("w-full flex-1 gap-3"):
            if not page_rows:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("group_off", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد كوادر مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching personnel found.").classes("text-xs app-text-muted")
            else:
                for row in page_rows:
                    self._render_card(row)

        disp_start = start_idx + 1 if total_count > 0 else 0
        disp_end = min(end_idx, total_count)

        with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
            prev_btn = UI.secondary_button("◄ السابق / Previous", on_click=self.go_prev).classes("text-xs px-4 py-2")
            if self.current_offset == 0 or self.search_term:
                prev_btn.disable()

            ui.label(f"السجلات {disp_start} - {disp_end} من {total_count}  |  Records {disp_start} - {disp_end} of {total_count}").classes("text-xs font-bold app-text-primary")

            next_btn = UI.secondary_button("التالي / Next ►", on_click=self.go_next).classes("text-xs px-4 py-2")
            if end_idx >= total_count or self.search_term:
                next_btn.disable()

    def _render_card(self, row: dict):
        pid = row["id"]
        is_active = row.get("is_active", 1)
        is_signature = bool(row.get("is_signature", 0))
        role = str(row.get("personnel_role") or "user")
        display_order = row.get("display_order", 0)
        
        title_ar = row.get("academic_title_ar") or ""
        name_ar = row.get("name_ar") or "—"
        full_display_name = f"{title_ar} {name_ar}".strip() if title_ar else name_ar
        resp_ar = row.get("responsibility_ar") or "—"

        with ui.row().classes(f"w-full items-center justify-between p-4 rounded-xl {'bg-[var(--bg-card)]' if is_active else 'bg-red-500/5'} border border-[var(--border-default)] gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("account_circle", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(full_display_name).classes("font-bold text-base app-text-primary truncate")
                    ui.label(f"@{row.get('username') or 'N/A'}  •  {resp_ar}").classes("text-xs text-slate-400 font-mono truncate")

            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("الصلاحية / Role").classes("text-[10px] app-text-muted font-semibold")
                    assigned_r_id = self.role_repo.get_user_role_id(pid, user_dict=row)
                    r_def = self.role_repo.get_by_id(assigned_r_id)
                    matched_r = r_def.get("name_ar") if r_def else assigned_r_id
                    ui.label(matched_r).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary")

                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("ترتيب التوقيع / Order").classes("text-[10px] app-text-muted font-semibold")
                    if is_signature and display_order and display_order > 0:
                        order_str = f"🖋️ {display_order}"
                        order_cls = "app-text-accent border-[var(--color-accent)]"
                    else:
                        order_str = "بدون توقيع"
                        order_cls = "app-text-muted border-[var(--border-default)]"
                    ui.label(order_str).classes(f"text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border {order_cls}")

            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                def toggle_act(r_id=pid, curr=is_active):
                    try:
                        self.repo.toggle_active(r_id, 0 if curr else 1)
                        UI.notify("تم تغيير حالة الكادر / State updated", type="positive")
                        self._render_content()
                    except OfflineModeError as err:
                        UI.notify(err, type="warning")
                    except Exception as err:
                        UI.notify(err, type="negative")

                if is_active:
                    UI.danger_button("تعطيل / Disable", on_click=toggle_act).classes("text-xs px-2 py-1.5")
                else:
                    UI.success_button("تفعيل / Enable", on_click=toggle_act).classes("text-xs px-2 py-1.5")

                UI.primary_button(
                    "",
                    icon="edit",
                    on_click=lambda r=row: self.show_edit_view(row=r, mode="edit")
                ).props("round dense").classes("text-xs p-1.5").tooltip("تعديل / Edit")

                UI.danger_button(
                    "",
                    icon="delete",
                    on_click=lambda r=row: self.confirm_delete(r)
                ).props("round dense").classes("text-xs p-1.5").tooltip("حذف / Delete")

    def go_prev(self):
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self._render_content()

    def go_next(self):
        self.current_offset += self.current_limit
        self._render_content()

    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        self.container.clear()
        existing_data = row or {}
        pid = existing_data.get("id")

        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden flex-col max-w-4xl mx-auto w-full"):
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] shrink-0"):
                    with ui.row().classes("items-center gap-3"):
                        ui.button(icon="arrow_back", on_click=self.show_list_view).props("flat round dense").classes("app-text-primary")
                        title_text = "إضافة كادر جديد — Add Personnel" if mode == "add" else f"تعديل الكادر — Edit {existing_data.get('name_ar', '')}"
                        ui.label(title_text).classes("text-xl font-bold app-text-primary")

                with ui.column().classes("w-full gap-6 overflow-y-auto pr-1"):
                    
                    # 1. Account Details
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("حساب الدخول — Account Details").classes("text-base font-bold app-text-accent")

                        with ui.row().classes("w-full gap-4 items-center"):
                            user_inp = UI.text_input(
                                "اسم المستخدم / Username",
                                value=existing_data.get("username", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                            pass_inp = UI.text_input(
                                "كلمة المرور / Password",
                                value=""
                            ).classes("flex-1 text-sm").props("type=password")

                            available_roles = self.role_repo.get_all()
                            role_options = {r["id"]: f"{r['name_ar']} / {r['name_en']}" for r in available_roles}
                            for k in ("user", "admin", "signer"):
                                if k not in role_options:
                                    role_options[k] = k

                            init_role = "user"
                            if existing_data:
                                pid = existing_data.get("id")
                                init_role = self.role_repo.get_user_role_id(pid) if pid else "user"

                            role_inp = UI.select(
                                "الدور والمسؤولية / Role & Responsibility",
                                options=role_options,
                                value=init_role
                            ).classes("w-72 text-sm")

                        # Dynamic summary tag for selected role capabilities
                        role_preview_label = ui.label("").classes("text-xs font-semibold text-emerald-400 mt-1")

                        def _update_role_preview(chosen_id):
                            r_info = self.role_repo.get_by_id(chosen_id)
                            if r_info:
                                p_cnt = len(r_info.get("allowed_pages", []))
                                a_cnt = len(r_info.get("allowed_actions", []))
                                d_scope = "كافة الأقسام" if (r_info.get("department_scope") == "all" or not r_info.get("department_scope")) else "أقسام مخصصة"
                                role_preview_label.set_text(f"🛡️ صلاحيات هذا الدور: {a_cnt} إجراء • {p_cnt} شاشات • نطاق الأقسام: {d_scope}")
                            else:
                                role_preview_label.set_text(f"الصلاحية: {chosen_id}")

                        role_inp.on_value_change(lambda e: _update_role_preview(e.value if hasattr(e, "value") else e))

                    # 2. Personal Info
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("المعلومات الشخصية — Personal Information").classes("text-base font-bold app-text-accent")

                        with ui.row().classes("w-full gap-4"):
                            name_ar_inp = UI.text_input("الاسم بالعربية / Arabic Name", value=existing_data.get("name_ar", "")).classes("flex-1 text-sm")
                            name_en_inp = UI.text_input("الاسم بالإنكليزية / English Name", value=existing_data.get("name_en", "")).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            title_ar_inp = UI.text_input("اللقب بالعربية / Arabic Title", value=existing_data.get("academic_title_ar", "")).classes("flex-1 text-sm")
                            title_en_inp = UI.text_input("اللقب بالإنكليزية / English Title", value=existing_data.get("academic_title_en", "")).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            resp_ar_inp = UI.text_input("المنصب بالعربية / Arabic Resp", value=existing_data.get("responsibility_ar", "")).classes("flex-1 text-sm")
                            resp_en_inp = UI.text_input("المنصب بالإنكليزية / English Resp", value=existing_data.get("responsibility_en", "")).classes("flex-1 text-sm")

                        # Initialize role preview with initial role
                        _update_role_preview(init_role)

                    # 3. Certificate Settings & Mapping
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("إعدادات الوثيقة والتوقيع — Document Position & Signature").classes("text-base font-bold app-text-accent")

                        # is_signature is derived from display_order: >0 means signatory
                        existing_order = int(existing_data.get("display_order") or 0)
                        init_is_sig = existing_order > 0

                        # Modern Toggle Switch placed ABOVE the dropdown list
                        is_sig_switch = UI.switch(
                            "يظهر كتوقيع في الوثيقة / Is Signature",
                            value=init_is_sig
                        ).classes("text-sm font-bold app-text-primary mb-2")

                        # Find matching label for the current display_order
                        order_key = next(
                            (k for k, v in ORDER_OPTIONS.items() if v == existing_order),
                            "بدون / None"
                        )

                        order_sel = UI.select(
                            "الموقع والتسلسل / Position & Order",
                            options={k: k for k in ORDER_OPTIONS.keys()},
                            value=order_key if init_is_sig else "بدون / None"
                        ).classes("w-64 text-sm")

                        # Dropdown only activates when toggle switch is ON
                        if not init_is_sig:
                            order_sel.disable()

                        def on_sig_switch_change(evt_args):
                            val = bool(evt_args.value if hasattr(evt_args, "value") else evt_args)
                            if val:
                                order_sel.enable()
                            else:
                                order_sel.value = "بدون / None"
                                order_sel.disable()

                        is_sig_switch.on_value_change(on_sig_switch_change)

                    with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] shrink-0"):
                        def save_action():
                            n_ar = (name_ar_inp.value or "").strip()
                            if not n_ar:
                                ui.notify("الاسم بالعربية مطلوب / Arabic name is required", type="warning")
                                return

                            pwd = pass_inp.value.strip() if pass_inp.value else None
                            if mode == "add" and not pwd:
                                ui.notify("كلمة المرور مطلوبة / Password is required", type="warning")
                                return

                            # ORDER_OPTIONS maps label→int; 0 when toggle is OFF
                            display_order = ORDER_OPTIONS.get(order_sel.value, 0) if is_sig_switch.value else 0

                            chosen_role_id = role_inp.value
                            sel_role = self.role_repo.get_by_id(chosen_role_id) or {}
                            base_role = sel_role.get("base_role", chosen_role_id if chosen_role_id in ("admin", "user", "signer") else "user")

                            resp_ar_val = (resp_ar_inp.value or "").strip()
                            resp_en_val = (resp_en_inp.value or "").strip()
                            if mode == "add":
                                if not resp_ar_val:
                                    resp_ar_val = sel_role.get("name_ar") or ""
                                if not resp_en_val:
                                    resp_en_val = sel_role.get("name_en") or ""

                            payload = {
                                "name_ar": n_ar,
                                "name_en": name_en_inp.value.strip() if name_en_inp.value else "",
                                "academic_title_ar": title_ar_inp.value.strip() if title_ar_inp.value else "",
                                "academic_title_en": title_en_inp.value.strip() if title_en_inp.value else "",
                                "responsibility_ar": resp_ar_val,
                                "responsibility_en": resp_en_val,
                                "display_order": display_order,
                                "username": user_inp.value.strip() if user_inp.value else "",
                                "personnel_role": base_role,
                                "is_active": existing_data.get("is_active", 1)
                            }

                            from nicegui_ui.state import app_session
                            from sync_engine import is_online
                            # A password an admin types for SOMEONE ELSE is temporary: they must change it at login
                            temp_pwd = bool(pwd) and (pid is None or int(pid) != int(app_session.emp_id))

                            if mode == "add" and pwd:
                                payload["password_hash"] = pwd
                                payload["must_change_password"] = True

                            try:
                                if mode == "add":
                                    new_id = self.repo.insert(data=payload)
                                    if new_id:
                                        self.role_repo.assign_role_to_personnel(int(new_id), chosen_role_id)
                                    ui.notify("تمت إضافة الكادر وتعيين صلاحيات الدور بنجاح / Personnel added", type="positive")
                                elif not is_online() and pwd and pid is not None:
                                    # Offline: only the password can be reset (temporary, queued for the server)
                                    self.repo.set_password(int(pid), pwd, must_change=temp_pwd)
                                    ui.notify(
                                        "تم تعيين كلمة مرور مؤقتة على هذا الجهاز، وسترسل للسيرفر عند الاتصال. "
                                        "باقي التعديلات تتطلب الاتصال. / Temporary password set on this PC (sent to the "
                                        "server when online). Other changes need a connection.",
                                        type="info", timeout=10000
                                    )
                                else:
                                    if pid is not None:
                                        self.repo.update(person_id=int(pid), data=payload)
                                        self.role_repo.assign_role_to_personnel(int(pid), chosen_role_id)
                                        if pwd:
                                            self.repo.set_password(int(pid), pwd, must_change=temp_pwd)
                                        app_session.refresh_access(int(pid))
                                    ui.notify("تم تعديل الكادر وتحديث صلاحيات الدور بنجاح / Personnel updated", type="positive")
                                self.show_list_view()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                log.error(f"Error saving personnel: {err}")
                                ui.notify(f"خطأ أثناء الحفظ: {err}", type="negative")

                        UI.secondary_button("إلغاء / Cancel", on_click=self.show_list_view).classes("text-sm px-5 py-2")
                        UI.success_button("حفظ / Save", icon="save", on_click=save_action).classes("text-sm px-5 py-2")

    def confirm_delete(self, row: dict):
        pid = row["id"]
        dialog = ui.dialog()
        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
            ui.label("تأكيد الحذف — Confirm Delete").classes("text-lg font-bold app-text-primary")
            warning = "تحذير: الكادر لا يزال نشطاً.\n" if row.get("is_active") else ""
            ui.label(
                f"{warning}هل أنت متأكد من حذف هذا السجل نهائياً؟\n{row.get('name_ar', '')}"
            ).classes("text-sm app-text-muted whitespace-pre-line")

            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                def do_delete():
                    try:
                        self.repo.delete(pid)
                        ui.notify("تم حذف السجل / Personnel deleted", type="positive")
                        dialog.close()
                        self.show_list_view()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        ui.notify(f"خطأ أثناء الحذف: {err}", type="negative")

                UI.danger_button("حذف / Delete", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()
