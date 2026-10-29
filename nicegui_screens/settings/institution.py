# =============================================================================
# nicegui_screens/settings/institution.py — Settings: institution info and logos
# =============================================================================

import os
from datetime import datetime
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import read_upload


class InstitutionMixin:
    """Institution names, university/college logos (part of SettingsScreen)."""

    def _section_institution_info(self) -> None:
        with UI.card():
            UI.card_header("معلومات المؤسسة — Institution Info", "domain", icon_css="stat-text-blue")

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.univ_ar_input = UI.text_input(
                    "اسم الجامعة بالعربية / Univ. Name (AR)",
                    value=self.settings_data.get("univ_name_ar") or ""
                )
                self.univ_en_input = UI.text_input(
                    "اسم الجامعة بالإنكليزية / Univ. Name (EN)",
                    value=self.settings_data.get("univ_name_en") or ""
                )
                self.college_ar_input = UI.text_input(
                    "اسم الكلية بالعربية / College Name (AR)",
                    value=self.settings_data.get("college_name_ar") or ""
                )
                self.college_en_input = UI.text_input(
                    "اسم الكلية بالإنجليزية / College Name (EN)",
                    value=self.settings_data.get("college_name_en") or ""
                )

            # ── LOGO UPLOAD & PREVIEW SECTION ─────────────────────────────────
            with ui.column().classes("w-full gap-3 pt-3 border-t border-[var(--border-default)] mt-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("image", size="sm").classes("text-blue-400")
                    ui.label("شعارات المؤسسة والكلية — Official Logos").classes("font-bold text-sm app-text-primary")
                    ui.label("(يدعم ملفات الصور بصيغ PNG, JPG, WebP, SVG)").classes("text-xs app-text-muted")

                with ui.grid(columns=2).classes("w-full gap-4"):
                    # 1. University Logo Tile
                    with ui.column().classes("p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] gap-3"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("account_balance", size="xs").classes("text-blue-400")
                                ui.label("شعار الجامعة / University Logo").classes("font-semibold text-xs app-text-primary")
                            self.univ_logo_status = ui.label(os.path.basename(self.univ_logo_path) if self.univ_logo_path else "").classes("text-[10px] app-text-muted font-mono truncate max-w-[150px]")

                        with ui.row().classes("w-full items-center justify-center p-3 rounded-xl border border-dashed border-[var(--border-default)] min-h-[110px] bg-[var(--surface-card)]"):
                            univ_src = self.univ_logo_path if (self.univ_logo_path and os.path.exists(self.univ_logo_path)) else None
                            if univ_src:
                                self.univ_logo_img = ui.image(f"{univ_src}?t={datetime.now().timestamp()}").classes("max-h-24 max-w-[140px] object-contain")
                                self.univ_placeholder_col = ui.column().classes("items-center justify-center gap-1 hidden")
                            else:
                                self.univ_logo_img = ui.image("").classes("max-h-24 max-w-[140px] object-contain hidden")
                                self.univ_placeholder_col = ui.column().classes("items-center justify-center gap-1")
                                with self.univ_placeholder_col:
                                    ui.icon("account_balance", size="md").classes("app-text-muted opacity-40")
                                    ui.label("لا يوجد شعار محدد").classes("text-[11px] app-text-muted")

                        async def _handle_univ_logo_upload(e):
                            try:
                                up_name, content = await read_upload(e)
                                if not content:
                                    ui.notify("تعذر قراءة الصورة!", type="warning")
                                    return
                                ext = os.path.splitext(up_name or "logo.png")[1].lower()
                                if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                                    ext = ".png"
                                os.makedirs("assets", exist_ok=True)
                                saved_path = f"assets/univ_logo{ext}"
                                with open(saved_path, "wb") as f_out:
                                    f_out.write(content)
                                self.univ_logo_path = saved_path
                                self.univ_logo_img.set_source(f"{saved_path}?t={datetime.now().timestamp()}")
                                self.univ_logo_img.classes(remove="hidden")
                                self.univ_placeholder_col.classes(add="hidden")
                                self.univ_logo_status.set_text(os.path.basename(saved_path))
                                ui.notify("تم استلام شعار الجامعة! اضغط على زر الحفظ بالأسفل لاعتماده.", type="positive")
                            except Exception as err:
                                ui.notify(f"خطأ في رفع الشعار: {err}", type="negative")

                        ui.upload(
                            label="اختر أو اسحب شعار الجامعة هنا",
                            auto_upload=True,
                            on_upload=_handle_univ_logo_upload
                        ).props("accept='image/png,image/jpeg,image/webp,image/svg+xml' max-files=1 flat dense").classes("w-full text-xs")

                    # 2. College Logo Tile
                    with ui.column().classes("p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] gap-3"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("school", size="xs").classes("text-emerald-400")
                                ui.label("شعار الكلية / College Logo").classes("font-semibold text-xs app-text-primary")
                            self.college_logo_status = ui.label(os.path.basename(self.college_logo_path) if self.college_logo_path else "").classes("text-[10px] app-text-muted font-mono truncate max-w-[150px]")

                        with ui.row().classes("w-full items-center justify-center p-3 rounded-xl border border-dashed border-[var(--border-default)] min-h-[110px] bg-[var(--surface-card)]"):
                            col_src = None
                            if self.college_logo_path and os.path.exists(self.college_logo_path):
                                col_src = self.college_logo_path
                            elif os.path.exists("assets/csit.png"):
                                col_src = "assets/csit.png"

                            if col_src:
                                self.college_logo_img = ui.image(f"{col_src}?t={datetime.now().timestamp()}").classes("max-h-24 max-w-[140px] object-contain")
                                self.college_placeholder_col = ui.column().classes("items-center justify-center gap-1 hidden")
                            else:
                                self.college_logo_img = ui.image("").classes("max-h-24 max-w-[140px] object-contain hidden")
                                self.college_placeholder_col = ui.column().classes("items-center justify-center gap-1")
                                with self.college_placeholder_col:
                                    ui.icon("school", size="md").classes("app-text-muted opacity-40")
                                    ui.label("لا يوجد شعار محدد").classes("text-[11px] app-text-muted")

                        async def _handle_college_logo_upload(e):
                            try:
                                up_name, content = await read_upload(e)
                                if not content:
                                    ui.notify("تعذر قراءة الصورة!", type="warning")
                                    return
                                ext = os.path.splitext(up_name or "logo.png")[1].lower()
                                if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                                    ext = ".png"
                                os.makedirs("assets", exist_ok=True)
                                saved_path = f"assets/college_logo{ext}"
                                with open(saved_path, "wb") as f_out:
                                    f_out.write(content)
                                self.college_logo_path = saved_path
                                self.college_logo_img.set_source(f"{saved_path}?t={datetime.now().timestamp()}")
                                self.college_logo_img.classes(remove="hidden")
                                self.college_placeholder_col.classes(add="hidden")
                                self.college_logo_status.set_text(os.path.basename(saved_path))
                                ui.notify("تم استلام شعار الكلية! اضغط على زر الحفظ بالأسفل لاعتماده.", type="positive")
                            except Exception as err:
                                ui.notify(f"خطأ في رفع الشعار: {err}", type="negative")

                        ui.upload(
                            label="اختر أو اسحب شعار الكلية هنا",
                            auto_upload=True,
                            on_upload=_handle_college_logo_upload
                        ).props("accept='image/png,image/jpeg,image/webp,image/svg+xml' max-files=1 flat dense").classes("w-full text-xs")

            with ui.row().classes("w-full justify-end items-center pt-3 border-t border-[var(--border-default)] mt-2"):
                UI.success_button(
                    "حفظ معلومات المؤسسة والشعارات / Save Info & Logos",
                    icon="save",
                    on_click=self._save_institution_info
                ).classes("px-5 py-2 text-xs font-bold")

    def _save_institution_info(self) -> None:
        try:
            self.s_repo.update_settings(
                univ_ar=(self.univ_ar_input.value if self.univ_ar_input else "") or "",
                univ_en=(self.univ_en_input.value if self.univ_en_input else "") or "",
                college_ar=(self.college_ar_input.value if self.college_ar_input else "") or "",
                college_en=(self.college_en_input.value if self.college_en_input else "") or "",
                univ_logo=self.univ_logo_path,
                college_logo=self.college_logo_path
            )
            ui.notify("تم حفظ معلومات المؤسسة والشعارات بنجاح / Institution info & logos saved!", type="positive")
        except Exception as exc:
            ui.notify(f"Error saving settings: {exc}", type="negative")
