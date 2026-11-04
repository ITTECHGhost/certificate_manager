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
    "بدون": 0,
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

        self.container = ui.column().classes("w-full gap-4")
        self.show_list_view()

    def show_list_view(self):
        """Personnel list: search and add in one row, read-only rows (click to edit), one paginator."""
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2"):
                    def on_search_change(e):
                        val = extract_event_value(e, default="")
                        self.search_term = str(val or "").strip().lower()
                        self.current_offset = 0
                        self._render_content()

                    UI.search_input(
                        placeholder="ابحث بالاسم أو اسم المستخدم",
                        on_change=on_search_change,
                    ).classes("flex-1 min-w-[220px] max-w-md")
                    ui.space()
                    UI.primary_button("إضافة كادر", icon="person_add", on_click=lambda: self.show_edit_view(mode="add"))

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
        if not all_rows:
            if self.search_term:
                UI.empty_state("لا يوجد كادر مطابق", "تحقق من الاسم أو امسح البحث.", icon="search_off")
            else:
                UI.empty_state("لا توجد كوادر بعد", "أضف أول كادر أو مستخدم.", icon="group_off",
                               action_text="إضافة كادر", on_action=lambda: self.show_edit_view(mode="add"))
            return

        self.current_offset = min(self.current_offset, (total_count - 1) // self.current_limit * self.current_limit)
        page_rows = all_rows[self.current_offset:self.current_offset + self.current_limit]

        rows = []
        for r in page_rows:
            title_ar = r.get("academic_title_ar") or ""
            name_ar = r.get("name_ar") or "—"
            assigned_r_id = self.role_repo.get_user_role_id(r["id"], user_dict=r)
            r_def = self.role_repo.get_by_id(assigned_r_id)
            display_order = r.get("display_order", 0) or 0
            signs = bool(r.get("is_signature", 0)) and display_order > 0
            role_name = str((r_def.get("name_ar") if r_def else assigned_r_id) or "")
            # Second line under the name: the role (permission set) and the username
            sub = " • ".join(x for x in (role_name, r.get("username") or "") if x)
            rows.append({
                "id": r["id"],
                "name": f"{title_ar} {name_ar}".strip(),
                "sub": sub,
                "position": r.get("responsibility_ar") or "—",
                # The signature chip appears only for people who actually sign documents
                "signature": f"يوقّع ({display_order})" if signs else "",
                "active": bool(r.get("is_active", 1)),
                "raw": r,
            })

        table = UI.data_table([
            {"name": "name", "label": "الاسم", "field": "name", "align": "right"},
            {"name": "position", "label": "المنصب", "field": "position"},
            {"name": "signature", "label": "التوقيع", "field": "signature"},
            {"name": "active", "label": "الحالة", "field": "active"},
            {"name": "actions", "label": "", "field": "actions"},
        ], rows, clickable=True)
        table.add_slot("body-cell-name", """
            <q-td :props="props">
                <div class="flex flex-col text-start leading-tight">
                    <span class="font-semibold app-text-primary">{{ props.row.name }}</span>
                    <span class="app-caption">{{ props.row.sub }}</span>
                </div>
            </q-td>
        """)
        table.add_slot("body-cell-signature", """
            <q-td :props="props">
                <span v-if="props.value" class="app-chip app-chip--accent">{{ props.value }}</span>
            </q-td>
        """)
        table.add_slot("body-cell-active", """
            <q-td :props="props">
                <span v-if="props.value" class="app-chip">نشط</span>
                <span v-else class="app-chip app-chip--warning">معطّل</span>
            </q-td>
        """)
        table.add_slot("body-cell-actions", """
            <q-td :props="props" auto-width>
                <q-btn flat round dense :icon="props.row.active ? 'person_off' : 'person'" class="app-btn-icon"
                       :aria-label="props.row.active ? 'تعطيل' : 'تفعيل'"
                       @click.stop="$parent.$emit('toggle_active', props.row)">
                    <q-tooltip>{{ props.row.active ? 'تعطيل' : 'تفعيل' }}</q-tooltip>
                </q-btn>
                <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف الكادر"
                       @click.stop="$parent.$emit('delete_person', props.row)">
                    <q-tooltip>حذف الكادر</q-tooltip>
                </q-btn>
            </q-td>
        """)
        table.on("rowClick", lambda e: self.show_edit_view(row=e.args[1].get("raw"), mode="edit"))
        table.on("toggle_active", lambda e: self._toggle_active(e.args))
        table.on("delete_person", lambda e: self.confirm_delete(e.args.get("raw") or e.args))

        UI.paginator(total_count, self.current_offset // self.current_limit + 1, self.current_limit, self._go_to_page)

    def _toggle_active(self, row: dict):
        name = row.get("name") or ""
        try:
            self.repo.toggle_active(row["id"], 0 if row.get("active") else 1)
            UI.notify(f"تم {'تعطيل' if row.get('active') else 'تفعيل'} ({name})", type="positive")
            self._render_content()
        except OfflineModeError as err:
            UI.notify(err, type="warning")
        except Exception as err:
            UI.notify(err, type="negative")

    def _go_to_page(self, page: int):
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
        self._render_content()

    def show_edit_view(self, row: dict | None = None, mode: str = "add"):
        self.container.clear()
        existing_data = row or {}
        pid = existing_data.get("id")

        with self.container:
            with UI.card().classes("gap-6 max-w-4xl mx-auto w-full"):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    UI.back_button(self.show_list_view)
                    title_text = "إضافة كادر جديد" if mode == "add" else f"تعديل الكادر {existing_data.get('name_ar', '')}"
                    ui.label(title_text).classes("app-page-title")

                with ui.column().classes("w-full gap-6"):
                    
                    # 1. Account Details
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("حساب الدخول").classes("app-section-title")

                        with ui.row().classes("w-full gap-4 items-center"):
                            user_inp = UI.text_input(
                                "اسم المستخدم",
                                value=existing_data.get("username", "") if existing_data else ""
                            ).classes("flex-1 text-sm")

                            pass_inp = UI.text_input(
                                "كلمة المرور",
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
                                "الدور والمسؤولية",
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
                        ui.label("المعلومات الشخصية").classes("app-section-title")

                        with ui.row().classes("w-full gap-4"):
                            name_ar_inp = UI.text_input("الاسم بالعربية", value=existing_data.get("name_ar", "")).classes("flex-1 text-sm")
                            name_en_inp = UI.text_input("الاسم بالإنكليزية", value=existing_data.get("name_en", "")).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            title_ar_inp = UI.text_input("اللقب بالعربية", value=existing_data.get("academic_title_ar", "")).classes("flex-1 text-sm")
                            title_en_inp = UI.text_input("اللقب بالإنكليزية", value=existing_data.get("academic_title_en", "")).classes("flex-1 text-sm")

                        with ui.row().classes("w-full gap-4"):
                            resp_ar_inp = UI.text_input("المنصب بالعربية", value=existing_data.get("responsibility_ar", "")).classes("flex-1 text-sm")
                            resp_en_inp = UI.text_input("المنصب بالإنكليزية", value=existing_data.get("responsibility_en", "")).classes("flex-1 text-sm")

                        # Initialize role preview with initial role
                        _update_role_preview(init_role)

                    # 3. Certificate Settings & Mapping
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("إعدادات الوثيقة والتوقيع").classes("app-section-title")

                        # is_signature is derived from display_order: >0 means signatory
                        existing_order = int(existing_data.get("display_order") or 0)
                        init_is_sig = existing_order > 0

                        # Modern Toggle Switch placed ABOVE the dropdown list
                        is_sig_switch = UI.switch(
                            "يظهر كتوقيع في الوثيقة",
                            value=init_is_sig
                        ).classes("text-sm font-bold app-text-primary mb-2")

                        # Find matching label for the current display_order
                        order_key = next(
                            (k for k, v in ORDER_OPTIONS.items() if v == existing_order),
                            "بدون"
                        )

                        order_sel = UI.select(
                            "الموقع والتسلسل",
                            options={k: k for k in ORDER_OPTIONS.keys()},
                            value=order_key if init_is_sig else "بدون"
                        ).classes("w-64 text-sm")

                        # Dropdown only activates when toggle switch is ON
                        if not init_is_sig:
                            order_sel.disable()

                        def on_sig_switch_change(evt_args):
                            val = bool(evt_args.value if hasattr(evt_args, "value") else evt_args)
                            if val:
                                order_sel.enable()
                            else:
                                order_sel.value = "بدون"
                                order_sel.disable()

                        is_sig_switch.on_value_change(on_sig_switch_change)

                    with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] shrink-0"):
                        def save_action():
                            n_ar = (name_ar_inp.value or "").strip()
                            if not n_ar:
                                ui.notify("الاسم بالعربية مطلوب", type="warning")
                                return

                            pwd = pass_inp.value.strip() if pass_inp.value else None
                            if mode == "add" and not pwd:
                                ui.notify("كلمة المرور مطلوبة", type="warning")
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
                                    ui.notify("تمت إضافة الكادر وتعيين صلاحيات الدور بنجاح", type="positive")
                                elif not is_online() and pwd and pid is not None:
                                    # Offline: only the password can be reset (temporary, queued for the server)
                                    self.repo.set_password(int(pid), pwd, must_change=temp_pwd)
                                    ui.notify(
                                        "تم تعيين كلمة مرور مؤقتة على هذا الجهاز، وسترسل للسيرفر عند الاتصال. "
                                        "باقي التعديلات تتطلب الاتصال.",
                                        type="info", timeout=10000
                                    )
                                else:
                                    if pid is not None:
                                        self.repo.update(person_id=int(pid), data=payload)
                                        self.role_repo.assign_role_to_personnel(int(pid), chosen_role_id)
                                        if pwd:
                                            self.repo.set_password(int(pid), pwd, must_change=temp_pwd)
                                        app_session.refresh_access(int(pid))
                                    ui.notify("تم تعديل الكادر وتحديث صلاحيات الدور بنجاح", type="positive")
                                self.show_list_view()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                log.error(f"Error saving personnel: {err}")
                                ui.notify(f"خطأ أثناء الحفظ: {err}", type="negative")

                        UI.ghost_button("إلغاء", on_click=self.show_list_view)
                        UI.primary_button("حفظ", icon="save", on_click=save_action)

    def confirm_delete(self, row: dict):
        pid = row["id"]
        name_ar = row.get("name_ar", "")
        warning = " الكادر ما يزال نشطًا." if row.get("is_active") else ""

        def do_delete():
            try:
                self.repo.delete(pid)
                UI.notify(f"تم حذف الكادر ({name_ar})", type="positive")
                self._render_content()
            except OfflineModeError as err:
                UI.notify(str(err), type="warning")
            except Exception as err:
                UI.notify(f"تعذر حذف الكادر: {err}", type="negative")

        UI.confirm_dialog(
            "حذف الكادر",
            f"سيُحذف الكادر ({name_ar}) نهائيًا.{warning} لا يمكن التراجع عن ذلك.",
            "حذف الكادر",
            do_delete,
        )
