import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import PersonnelRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)

ORDER_OPTIONS = {
    "1": (1, "front"),
    "2": (2, "front"),
    "3": (3, "front"),
    "4": (4, "front"),
    "5": (5, "back"),
    "6": (6, "back"),
    "7": (7, "back"),
    "8": (8, "back"),
    "9": (9, "back"),
    "10": (10, "back"),
    "بدون / None": (0, "front"),
}

class PersonnelScreen:
    """
    Personnel Management Screen (NiceGUI version).
    Uses full page views for list and edit modes.
    """

    def __init__(self):
        self.repo = PersonnelRepository()
        self.current_limit = 25
        self.current_offset = 0
        self.search_term = ""

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.show_list_view()

    def show_list_view(self):
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1 gap-6 p-6 overflow-hidden"):
                # Header Bar
                with ui.row().classes("w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header"):
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
                with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
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
            fetch_limit = 500 if self.search_term else self.current_limit
            fetch_offset = 0 if self.search_term else self.current_offset
            rows = self.repo.get_all() or [] # repo doesn't support limit yet natively
            
            # Apply manual limit/offset since repo.get_all doesn't take args currently
            if self.search_term:
                t = self.search_term
                filtered = [
                    r for r in rows
                    if t in str(r.get("name_ar") or "").lower()
                    or t in str(r.get("username") or "").lower()
                ]
                return filtered[fetch_offset:fetch_offset + fetch_limit]
            
            return rows[fetch_offset:fetch_offset + fetch_limit]
            
        except Exception as err:
            log.warning(f"Failed to fetch personnel: {err}")
            return []

    def _build_table(self):
        rows = self._get_filtered_data()

        with ui.column().classes("w-full flex-1 gap-3 overflow-y-auto min-h-[340px]"):
            if not rows:
                with ui.column().classes("w-full items-center py-12 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                    ui.icon("group_off", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد كوادر مطابقة").classes("text-lg font-bold app-text-muted")
                    ui.label("No matching personnel found.").classes("text-xs app-text-muted")
            else:
                for row in rows:
                    self._render_card(row)

        start_idx = self.current_offset + 1 if rows else 0
        
        try:
            total_rows = len(self.repo.get_all() or [])
        except:
            total_rows = len(rows)

        end_idx = min(self.current_offset + self.current_limit, total_rows)

        with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] shrink-0"):
            prev_btn = UI.secondary_button("◄ السابق / Previous", on_click=self.go_prev).classes("text-xs px-4 py-2")
            if self.current_offset == 0 or self.search_term:
                prev_btn.disable()

            ui.label(f"السجلات {start_idx} - {end_idx} من {total_rows}").classes("text-sm font-bold app-text-primary")

            next_btn = UI.secondary_button("التالي / Next ►", on_click=self.go_next).classes("text-xs px-4 py-2")
            if end_idx >= total_rows or self.search_term:
                next_btn.disable()

    def _render_card(self, row: dict):
        pid = row["id"]
        is_active = row.get("is_active", 1)
        role = str(row.get("personnel_role") or "user")
        display_order = row.get("display_order", 0)

        with ui.row().classes(f"w-full items-center justify-between p-4 rounded-xl {'bg-[var(--bg-card)]' if is_active else 'bg-red-500/5'} border border-[var(--border-default)] gap-4 flex-nowrap overflow-hidden hover:border-[var(--color-accent)] transition-all shadow-sm"):
            with ui.row().classes("items-center gap-4 flex-1 min-w-0"):
                ui.icon("account_circle", size="md").classes("app-text-accent shrink-0")
                with ui.column().classes("gap-0 min-w-0 flex-1"):
                    ui.label(row.get("name_ar") or "—").classes("font-bold text-base app-text-primary truncate")
                    ui.label(f"@{row.get('username') or 'N/A'}").classes("text-xs text-slate-400 font-mono truncate")

            with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("الصلاحية / Role").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(role).classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-primary")

                with ui.column().classes("items-center gap-0 shrink-0 text-center"):
                    ui.label("ترتيب التوقيع / Signature Order").classes("text-[10px] app-text-muted font-semibold")
                    ui.label(str(display_order) if display_order > 0 else "بدون").classes("text-xs font-bold px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent")

            with ui.row().classes("items-center gap-2 shrink-0 flex-nowrap"):
                def toggle_act(r_id=pid, curr=is_active):
                    try:
                        self.repo.toggle_active(r_id, 0 if curr else 1)
                        ui.notify("تم تغيير حالة الكادر / State updated", type="positive")
                        self._render_content()
                    except Exception as err:
                        ui.notify(f"Error toggling state: {err}", type="negative")

                if is_active:
                    UI.danger_button("تعطيل / Disable", on_click=toggle_act).classes("text-xs px-2 py-1.5")
                else:
                    UI.success_button("تفعيل / Enable", on_click=toggle_act).classes("text-xs px-2 py-1.5")

                UI.primary_button(
                    "تعديل / Edit",
                    icon="edit",
                    on_click=lambda r=row: self.show_edit_view(row=r, mode="edit")
                ).classes("text-xs px-3 py-1.5")

                UI.danger_button(
                    icon="delete",
                    on_click=lambda r=row: self.confirm_delete(r)
                ).classes("text-xs px-2 py-1.5")

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

                            role_inp = UI.select(
                                "الصلاحية / Role",
                                options={"user": "مستخدم / User", "admin": "مسؤول / Admin"},
                                value=existing_data.get("personnel_role", "user") if existing_data else "user"
                            ).classes("w-48 text-sm")

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

                    # 3. Certificate Settings
                    with UI.card().classes("w-full p-5 gap-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] shrink-0"):
                        ui.label("الموقع في الوثيقة — Document Position").classes("text-base font-bold app-text-accent")

                        existing_order = existing_data.get("display_order", 0)
                        order_key = "بدون / None"
                        for k, v in ORDER_OPTIONS.items():
                            if v[0] == existing_order:
                                order_key = k
                                break

                        order_sel = UI.select(
                            "التسلسل / Order",
                            options={k: k for k in ORDER_OPTIONS.keys()},
                            value=order_key
                        ).classes("w-64 text-sm")

                    with ui.row().classes("w-full justify-end gap-3 pt-4 border-t border-[var(--border-default)] shrink-0"):
                        def save_action():
                            n_ar = name_ar_inp.value.strip() if name_ar_inp.value else ""
                            if not n_ar:
                                ui.notify("الاسم بالعربية مطلوب / Arabic name is required", type="warning")
                                return

                            pwd = pass_inp.value.strip() if pass_inp.value else None
                            if mode == "add" and not pwd:
                                ui.notify("كلمة المرور مطلوبة / Password is required", type="warning")
                                return

                            selected_order = ORDER_OPTIONS[order_sel.value]

                            payload = {
                                "name_ar": n_ar,
                                "name_en": name_en_inp.value.strip() if name_en_inp.value else "",
                                "academic_title_ar": title_ar_inp.value.strip() if title_ar_inp.value else "",
                                "academic_title_en": title_en_inp.value.strip() if title_en_inp.value else "",
                                "responsibility_ar": resp_ar_inp.value.strip() if resp_ar_inp.value else "",
                                "responsibility_en": resp_en_inp.value.strip() if resp_en_inp.value else "",
                                "display_order": selected_order[0],
                                "page_location": selected_order[1],
                                "username": user_inp.value.strip() if user_inp.value else "",
                                "personnel_role": role_inp.value,
                                "is_active": existing_data.get("is_active", 1)
                            }

                            if pwd:
                                payload["password_hash"] = pwd # Simple hash fallback managed by repo or API

                            try:
                                if mode == "add":
                                    self.repo.insert(data=payload)
                                    ui.notify("تمت الإضافة بنجاح / Personnel added", type="positive")
                                else:
                                    # If not updating password, don't pass empty string
                                    if not pwd:
                                        payload["password_hash"] = existing_data.get("password_hash")
                                        
                                    self.repo.update(person_id=pid, data=payload)
                                    ui.notify("تم التعديل بنجاح / Personnel updated", type="positive")
                                self.show_list_view()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                log.error(f"Error saving personnel: {err}")
                                ui.notify(f"Error: {err}", type="negative")

                        UI.secondary_button("إلغاء / Cancel", on_click=self.show_list_view).classes("text-sm px-5 py-2")
                        UI.success_button("💾 حفظ / Save", icon="save", on_click=save_action).classes("text-sm px-5 py-2")

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
                        ui.notify(f"خطأ في الحذف / Cannot delete: {err}", type="negative")

                UI.danger_button("حذف / Delete", icon="delete", on_click=do_delete).classes("text-sm px-4 py-2")
                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
        dialog.open()
