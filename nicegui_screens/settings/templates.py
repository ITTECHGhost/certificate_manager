# =============================================================================
# nicegui_screens/settings/templates.py — Settings: certificate Word templates
# =============================================================================

import os
import logging
from datetime import datetime
from nicegui import ui
import app_paths
from nicegui_ui.ui_components import UI
from nicegui_ui.template_constants import (
    TAG_LANGS, TAG_MARKS, TAG_SYSTEMS, get_template_info, save_template_tags, template_tag_conflicts, template_tags,
)
from utils.file_delivery import deliver_file
from nicegui_ui.upload_utils import read_upload

log = logging.getLogger(__name__)


class TemplatesMixin:
    """Template legend, catalog (rename/open/download), server sync and upload (part of SettingsScreen)."""

    def _section_templates_management(self) -> None:
        """Dedicated settings tab to inspect, manage, upload, and understand certificate Word templates."""
        templates_dir = str(app_paths.data_path("templets"))
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir, exist_ok=True)

        # ── 1. Guide & Abbreviations Legend Card ──────────────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("menu_book", size="md").classes("stat-text-blue")
                    with ui.column().classes("gap-0"):
                        ui.label("دليل معاني واختصارات أسماء القوالب").classes("text-base font-bold app-text-primary")
                        ui.label("توضيح معايير التسمية المعتمدة لقوالب الوثائق: [اللغة]، [النظام / الدرجة]، [SBS إن وجد]، cr").classes("text-xs app-text-muted")

            with ui.grid(columns=4).classes("w-full gap-3 pt-2"):
                legends = [
                    ("En", "اللغة الإنكليزية", "English Language", "text-cyan-400", "language"),
                    ("Ar", "اللغة العربية", "Arabic Language", "text-emerald-400", "translate"),
                    ("Semester", "نظام المقررات (فصلي)", "Semester Course System", "text-teal-400", "view_timeline"),
                    ("Annual", "النظام السنوي", "Annual / Yearly System", "text-indigo-400", "calendar_today"),
                    ("Master", "الماجستير (دراسات عليا)", "Master's Degree Program", "text-purple-400", "school"),
                    ("SBS", "درجات مقترنة جنباً إلى جنب", "Side-By-Side Courses", "text-amber-400", "view_column"),
                    ("cr", "وثيقة تخرج رسمية", "Official Certificate", "text-blue-400", "verified"),
                    ("Temp", "ملف قالب Word رسمي", "Word Template File (.docx)", "text-slate-400", "description"),
                ]
                for code, ar_label, en_label, color, icon in legends:
                    with ui.row().classes("items-center gap-2.5 p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                        ui.icon(icon, size="sm").classes(color)
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-1.5"):
                                ui.label(code).classes(f"font-bold font-mono text-xs {color}")
                                ui.label(f"— {ar_label}").classes("text-xs font-semibold app-text-primary")
                            ui.label(en_label).classes("text-[10px] app-text-muted")

        # ── 2. Templates Management & File Catalog Card ──────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] flex-wrap gap-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("article", size="md").classes("stat-text-purple")
                    with ui.column().classes("gap-0"):
                        ui.label("قوالب الوثائق الرسمية المتوفرة").classes("text-base font-bold app-text-primary")
                        ui.label("إدارة ملفات نماذج Word، تعديل مسمياتها المعتمدة، وفتحها مباشرة في Microsoft Word").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    def _open_templates_dir():
                        folder_path = os.path.abspath(templates_dir)
                        if os.path.exists(folder_path):
                            try:
                                os.startfile(folder_path)
                                ui.notify(f"تم فتح مجلد القوالب: {folder_path}", type="positive")
                            except Exception as e:
                                ui.notify(f"تعذر فتح المجلد: {e}", type="warning")

                    async def _sync_templates_from_server():
                        from sync_engine import is_online
                        if not is_online():
                            ui.notify("لا يمكن المزامنة في الوضع غير المتصل", type="warning")
                            return
                        n = ui.notification("جاري مزامنة نماذج الوثائق مع الخادم المركزي...", timeout=None, spinner=True)
                        try:
                            from nicegui import run
                            import services.template_sync as t_sync
                            res = await run.io_bound(t_sync.sync_templates_if_online)
                            n.dismiss()
                            if res.get("synced_files"):
                                ui.notify(f"تم تحديث {len(res['synced_files'])} ملف بنجاح", type="positive")
                                _render_templates_table.refresh()
                            elif res.get("up_to_date"):
                                ui.notify("جميع القوالب محدثة ومطابقة للخادم المركزي", type="info")
                            else:
                                ui.notify(f"فشلت مزامنة بعض الملفات: {res.get('errors')}", type="negative")
                        except Exception as e:
                            n.dismiss()
                            ui.notify(f"خطأ أثناء المزامنة: {e}", type="negative")

                    ui.button("مزامنة مع الخادم", icon="cloud_sync", on_click=_sync_templates_from_server).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")
                    ui.button("فتح مجلد القوالب", icon="folder_open", on_click=_open_templates_dir).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")
                    ui.button("تحديث", icon="refresh", on_click=lambda: _render_templates_table.refresh()).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")

            @ui.refreshable
            def _render_templates_table():
                files = []
                if os.path.exists(templates_dir):
                    files = [f for f in sorted(os.listdir(templates_dir)) if f.endswith(".docx") and not f.startswith("~")]

                if not files:
                    with ui.column().classes("w-full py-8 items-center justify-center gap-2 text-center"):
                        ui.icon("folder_off", size="xl").classes("app-text-muted")
                        ui.label("لم يتم العثور على أية قوالب Word في مجلد القوالب").classes("text-sm font-semibold app-text-primary")
                        ui.label("يمكنك إضافة ورفع القوالب أدناه مع تحديد مسمياتها الرسمية").classes("text-xs app-text-muted")
                    return

                with ui.column().classes("w-full gap-2 pt-2"):
                    for f in files:
                        filepath = os.path.join(templates_dir, f)
                        info = get_template_info(f)
                        tags = template_tags(f)
                        display_name = info.get("display_name") or f
                        size_kb = round(os.path.getsize(filepath) / 1024, 1)
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
                        conflicts = template_tag_conflicts(display_name, tags)

                        with ui.row().classes("app-template-card w-full items-center no-wrap gap-3"):
                            ui.icon("description", size="sm").classes("app-text-accent shrink-0")
                            with ui.column().classes("gap-1 flex-1 min-w-0"):
                                # The user's name with its tags right beside it
                                with ui.row().classes("items-center gap-2 flex-wrap"):
                                    ui.label(display_name).classes("app-text-primary font-semibold")
                                    for chip in (tags["system_ar"], tags["lang_ar"], tags["marks_ar"]):
                                        ui.label(chip).classes("app-chip app-chip--accent")
                                    for msg in conflicts:
                                        with ui.label("تعارض").classes("app-chip app-chip--warning"):
                                            ui.tooltip(msg)
                                ui.label(f"{f} • {size_kb} KB • آخر تعديل: {mtime}").classes("app-caption")

                            with ui.row().classes("items-center gap-1 shrink-0"):
                                UI.icon_button("edit", "تعديل الاسم والوسوم",
                                               on_click=lambda _e, fn=f, nm=display_name: _open_edit_dialog(fn, nm))

                                def _open_word(fp=filepath):
                                    try:
                                        os.startfile(os.path.abspath(fp))
                                        ui.notify(f"تم فتح القالب في Microsoft Word: {os.path.basename(fp)}", type="positive")
                                    except Exception as exc:
                                        ui.notify(f"تعذر فتح الملف: {exc}", type="warning")

                                UI.icon_button("launch", "فتح القالب في Word", on_click=lambda _e, fp=filepath: _open_word(fp))
                                UI.icon_button("download", "تنزيل القالب", on_click=lambda _e, fp=filepath: deliver_file(
                                    fp, filename=os.path.basename(fp),
                                    title=f"تم حفظ القالب ({os.path.basename(fp)}) بنجاح", auto_open=False))

            def _open_edit_dialog(filename: str, current_name: str):
                """Name and the three tags of one template; the .docx file is not changed."""
                t = template_tags(filename)
                with ui.dialog() as dlg, UI.card().classes("w-[520px] max-w-full gap-4"):
                    UI.card_header("تعديل القالب", "edit")
                    UI.muted_label(f"الملف: {filename}")
                    name_inp = UI.text_input("اسم القالب", value=current_name)
                    with ui.element("div").classes("app-template-tags w-full"):
                        lang_sel = UI.select("اللغة", dict(TAG_LANGS), value=t["lang"])
                        sys_sel = UI.select("النظام الدراسي", dict(TAG_SYSTEMS), value=t["system"])
                        marks_sel = UI.select("الدرجات", {True: TAG_MARKS[True], False: TAG_MARKS[False]}, value=t["sbs"])

                    def _save():
                        name = (name_inp.value or "").strip()
                        if not name:
                            ui.notify("اكتب اسم القالب", type="warning")
                            return
                        if save_template_tags(filename, name, lang_sel.value, sys_sel.value, bool(marks_sel.value)):
                            ui.notify("تم حفظ القالب", type="positive")
                            dlg.close()
                            _render_templates_table.refresh()
                        else:
                            ui.notify("تعذر حفظ القالب", type="negative")

                    with ui.row().classes("app-dialog-actions"):
                        UI.ghost_button("إلغاء", on_click=dlg.close)
                        UI.primary_button("حفظ", icon="save", on_click=_save)
                dlg.open()

            _render_templates_table()

        # ── 3. Add New Template & Choose Name Card ───────────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("add_circle", size="md").classes("stat-text-emerald")
                    with ui.column().classes("gap-0"):
                        ui.label("إضافة قالب وثيقة جديد وتحديد اسمه").classes("text-base font-bold app-text-primary")
                        ui.label("ارفع ملف Word (.docx)، واكتب اسمه، واختر لغته ونظامه الدراسي وهل هو بالدرجات.").classes("text-xs app-text-muted")

            new_template_state = {"file_name": "", "file_content": None}

            with ui.column().classes("w-full gap-4 pt-2"):
                name_input = UI.text_input("اسم القالب", placeholder="مثال: تأييد عربي سنوي")
                with ui.element("div").classes("app-template-tags w-full"):
                    add_lang = UI.select("اللغة", dict(TAG_LANGS), value="Ar")
                    add_sys = UI.select("النظام الدراسي", dict(TAG_SYSTEMS), value="Annual")
                    add_marks = UI.select("الدرجات", {True: TAG_MARKS[True], False: TAG_MARKS[False]}, value=False)

                # Selected file status indicator
                file_status_label = ui.label("لم يتم اختيار ملف Word بعد").classes("text-xs app-text-muted italic")

                async def _handle_upload(e):
                    try:
                        fname, content = await read_upload(e)
                        if not fname.lower().endswith(".docx"):
                            ui.notify("الملف غير مدعوم! يجب أن يكون ملف Word بتنسيق docx.", type="warning")
                            return

                        if not content:
                            ui.notify("تعذر قراءة محتوى الملف المرفوع", type="warning")
                            return

                        new_template_state["file_name"] = fname
                        new_template_state["file_content"] = content
                        file_status_label.set_text(f"تم اختيار الملف: {fname} ({round(len(content)/1024, 1)} KB)")
                        file_status_label.classes(remove="italic app-text-muted", add="font-bold text-emerald-400")
                        ui.notify(f"تم استلام ملف القالب: {fname}، اضغط على زر الحفظ أدناه لتسجيله", type="positive")
                    except Exception as up_err:
                        log.error(f"Failed to handle upload: {up_err}")
                        ui.notify(f"خطأ أثناء قراءة الملف: {up_err}", type="negative")

                ui.upload(
                    label="اختر أو اسحب ملف قالب Word (.docx) هنا",
                    auto_upload=True,
                    on_upload=_handle_upload
                ).props("accept=.docx max-files=1").classes("w-full border-2 border-dashed border-[var(--border-default)] rounded-2xl p-3 bg-[var(--bg-main)]")

                # Save Button Row
                with ui.row().classes("w-full justify-end items-center gap-2 pt-2"):
                    def _save_new_template():
                        fname = new_template_state.get("file_name")
                        content = new_template_state.get("file_content")
                        chosen_name = (name_input.value or "").strip()

                        if not fname or not content:
                            ui.notify("يرجى اختيار ملف Word (.docx) أولاً قبل الحفظ!", type="warning")
                            return

                        if not chosen_name:
                            ui.notify("يرجى إدخال اسم للقالب!", type="warning")
                            return

                        dest_path = os.path.join(templates_dir, fname)
                        try:
                            with open(dest_path, "wb") as f_out:
                                f_out.write(content)

                            save_template_tags(fname, chosen_name, add_lang.value, add_sys.value, bool(add_marks.value))

                            ui.notify(f"تم حفظ وتسجيل القالب بنجاح باسم: ({chosen_name})", type="positive")
                            new_template_state["file_name"] = ""
                            new_template_state["file_content"] = None
                            file_status_label.set_text("لم يتم اختيار ملف Word بعد")
                            file_status_label.classes(remove="font-bold text-emerald-400", add="italic app-text-muted")
                            _render_templates_table.refresh()
                        except Exception as err:
                            log.error(f"Failed to save new template: {err}")
                            ui.notify(f"خطأ أثناء حفظ القالب: {err}", type="negative")

                    UI.primary_button(
                        "حفظ وتسجيل القالب",
                        icon="save",
                        on_click=_save_new_template
                    ).classes("text-xs px-4 py-2")
