# =============================================================================
# nicegui_screens/scanned_orders_import_screen.py — «استيراد الأوامر الممسوحة» (admins)
# Gemini's CSV files of scanned graduation orders -> review -> students saved and linked to their
# order (services/scanned_orders_import.py). Online only. One request per order, all-or-nothing.
# =============================================================================

from pathlib import Path

from nicegui import background_tasks, run, ui

from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import read_upload, clear_when_done
from services import scanned_orders_import as soi
from utils.file_delivery import deliver_file

IMPORTABLE = (soi.EXACT, soi.VARIANT, soi.NEW)
STATUS_COLOR = {soi.EXACT: "green", soi.VARIANT: "teal", soi.NEW: "orange",
                soi.AMBIGUOUS: "red", soi.NO_DEPT: "red", soi.DUPLICATE: "grey"}
GENDERS = {1: "ذكر", 2: "أنثى"}


class ScannedOrdersImportScreen:
    def __init__(self):
        self.files: list[tuple[str, str]] = []
        self.result = None
        self.container = ui.column().classes("w-full gap-4")
        self.show()

    # ── step 1: files ────────────────────────────────────────────────────────
    def show(self):
        self.container.clear()
        with self.container:
            self._scan_card()
        with self.container, UI.card().classes("gap-3"):
            ui.label("استيراد الأوامر الممسوحة").classes("app-section-title")
            ui.label("ارفع ملفات CSV التي أخرجها الذكاء الاصطناعي من صور أوامر التخرج (ملف لكل أمر). يطابق البرنامج "
                     "الأسماء مع الطلاب المحفوظين، ويضيف الجدد بقيم افتراضية (محل الولادة البصرة، الجنسية "
                     "العراق) لتُكمل لاحقًا. لا تُنشأ سنوات دراسية؛ يُربط الطالب بأمر تخرجه فقط."
                     ).classes("app-caption")
            self.files_label = ui.label("لم تُرفع ملفات بعد.").classes("text-sm")

            async def on_upload(e):
                name, data = await read_upload(e)
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    UI.notify(f"{name}: ترميز الملف غير صحيح. احفظه من المفكرة بترميز يونيكود.", type="negative")
                    return
                self.files = [f for f in self.files if f[0] != name] + [(name, text)]
                self.files_label.set_text("الملفات: " + "، ".join(n for n, _ in self.files))

            clear_when_done(ui.upload(label="ملفات CSV", multiple=True, auto_upload=True,
                                      on_upload=on_upload).props('accept=".csv" flat bordered').classes("w-full"))
            with ui.row().classes("gap-2"):
                UI.primary_button("تحليل ومطابقة", icon="manage_search", on_click=self.analyse)
                UI.ghost_button("مسح الملفات", icon="delete_sweep", on_click=self._clear)
        with self.container:
            self.review_box = ui.column().classes("w-full gap-4")

    # ── step 0: scan the papers ─────────────────────────────────────────────
    def _scan_card(self, title: str = "مسح أوراق الأوامر بالماسح",
                   hint: str = "ضع أوراق الأمر الواحد (الصفحة الأولى أولًا) ثم اضغط «مسح». تُحفظ الصفحات في مجلد "
                               "جديد؛ أعطِها للذكاء الاصطناعي ليُخرج ملف CSV ثم ارفعه أدناه."):
        from services import scanner
        with UI.card().classes("gap-3"):
            ui.label(title).classes("app-section-title")
            ui.label(hint).classes("app-caption")
            with ui.row().classes("w-full items-end gap-2"):
                dev = UI.select("الماسح", options={}, value=None).classes("w-72", remove="w-full")
                src = ui.toggle(scanner.SOURCES, value="feeder").props("no-caps unelevated toggle-color=primary")
                dpi = UI.select("الدقة", options=scanner.DPI_OPTIONS, value=300).classes("w-36", remove="w-full")
                ftype = UI.select("نوع الملف", options=scanner.FILE_TYPES, value="pdf").classes("w-40", remove="w-full")
                size = UI.select("حجم الورقة", options=scanner.PAGE_SIZES, value="A4").classes("w-36", remove="w-full")
                color = ui.checkbox("ملوّن", value=True)
            status = ui.label("").classes("text-sm")

            async def find():
                try:
                    found = await run.io_bound(scanner.list_scanners)
                except Exception as err:
                    UI.notify(f"تعذر البحث عن الماسحات: {err}", type="negative")
                    return
                dev.options = found
                dev.value = next(iter(found), None)
                dev.update()
                status.set_text(f"وُجد {len(found)} ماسح." if found else
                                "لم يُعثر على ماسح: تأكد أنه مشغّل ومتصل ومُعرَّف في ويندوز.")

            async def scan():
                if not dev.value:
                    UI.notify("اختر الماسح أولًا (زر «البحث عن الماسحات»)", type="warning")
                    return
                status.set_text("جارٍ المسح... لا تُغلق البرنامج.")
                scan_btn.disable()
                try:
                    folder, pages = await run.io_bound(
                        lambda: scanner.scan_pages(dev.value, src.value, int(dpi.value or 300), bool(color.value),
                                                   file_type=ftype.value or "pdf", page_size=size.value or "A4"))
                except Exception as err:
                    status.set_text("")
                    UI.notify(f"تعذر المسح: {err}", type="negative")
                    return
                finally:
                    scan_btn.enable()
                self.last_scan = folder
                status.set_text(f"حُفظ المسح في: {folder}")
                UI.notify("تم المسح" if ftype.value == "pdf" else f"مُسحت {len(pages)} صفحة", type="positive")

            def open_folder():
                try:
                    scanner.open_folder(getattr(self, "last_scan", None))
                except Exception as err:
                    UI.notify(f"تعذر فتح المجلد: {err}", type="negative")

            with ui.row().classes("gap-2"):
                UI.ghost_button("البحث عن الماسحات", icon="search", on_click=find)
                scan_btn = UI.primary_button("مسح", icon="scanner", on_click=scan)
                UI.secondary_button("فتح مجلد المسح", icon="folder_open", on_click=open_folder)
                ocr = UI.ghost_button("قراءة آلية دون إنترنت (لاحقًا)", icon="smart_toy")
                ocr.disable()
                ocr.tooltip("نموذج قراءة محلي يُضاف لاحقًا؛ الآن استعمل الذكاء الاصطناعي لإخراج ملف CSV")

    def _clear(self):
        self.files, self.result = [], None
        self.show()

    async def analyse(self):
        if not self.files:
            UI.notify("ارفع ملف CSV واحدًا على الأقل", type="warning")
            return
        try:
            self.result = await run.io_bound(soi.analyse, list(self.files))
        except Exception as err:
            UI.notify(f"تعذر التحليل: {err}", type="negative")
            return
        self.render_review()

    # ── step 2: review ───────────────────────────────────────────────────────
    def render_review(self):
        res = self.result
        self.review_box.clear()
        counts = {}
        for r in res.review:
            counts[r["الحالة"]] = counts.get(r["الحالة"], 0) + 1
        with self.review_box:
            with UI.card().classes("gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("النتيجة").classes("app-section-title")
                    for k, v in counts.items():
                        ui.badge(f"{k}: {v}").props(f"color={STATUS_COLOR.get(k, 'grey')}")
                    ui.space()
                    UI.secondary_button("تصدير للمراجعة (Excel)", icon="file_download",
                                        on_click=lambda: deliver_file(soi.review_xlsx(res), "مراجعة_الأوامر.xlsx",
                                                                      title="تم تصدير ملف المراجعة"))
                created = soi.new_orders(res)
                if created:
                    with ui.row().classes("app-chip--accent w-full items-start gap-2 no-wrap rounded-lg p-3"):
                        ui.icon("add_circle", size="20px").classes("shrink-0")
                        ui.label("أوامر جديدة ستُنشأ أولًا ثم يُربط بها طلابها: "
                                 + "، ".join(f"{o['رقم الأمر']} ({o['القسم']}، {o['التاريخ']})" for o in created)
                                 ).classes("text-sm")
                missing = soi.missing_orders(res)
                if missing:
                    with ui.row().classes("app-chip--warning w-full items-start gap-2 no-wrap rounded-lg p-3"):
                        ui.icon("warning", size="20px").classes("shrink-0")
                        ui.label("أوامر بلا تاريخ في الورقة، لا يمكن إنشاؤها (يُحفظ طلابها دون ربط حتى تُنشأ في «أوامر التخرج»): "
                                 + "، ".join(f"{o['رقم الأمر']} ({o['القسم']})" for o in missing)).classes("text-sm")

            # importable rows, all ticked; click a row to fix its name / gender
            with UI.card().classes("gap-2"):
                ui.label("الأسماء القابلة للاستيراد (أزل العلامة عمّا لا تريده، واضغط الصف للتصحيح)"
                         ).classes("font-bold app-text-primary")
                rows = [self._row(i, it) for i, it in enumerate(res.items)]
                table = ui.table(columns=[
                    {"name": "status", "label": "الحالة", "field": "status", "align": "right"},
                    {"name": "order", "label": "رقم الأمر", "field": "order"},
                    {"name": "paper", "label": "الاسم في الورقة", "field": "paper", "align": "right"},
                    {"name": "name", "label": "يُحفظ باسم", "field": "name", "align": "right"},
                    {"name": "gender", "label": "الجنس", "field": "gender"},
                    {"name": "average", "label": "المعدل", "field": "average"},
                    {"name": "missing", "label": "يحتاج إكمال", "field": "missing", "align": "right"},
                ], rows=rows, row_key="key", selection="multiple",
                    pagination={"rowsPerPage": 50}).classes("w-full")
                table.selected = list(rows)
                table.on("rowClick", lambda e: self._edit_row(e.args[1], table))
                self.table = table
                with ui.row().classes("gap-2"):
                    UI.primary_button("استيراد المحدد", icon="cloud_upload", on_click=self.confirm_import)

            skipped = [r for r in res.review if r["الحالة"] not in IMPORTABLE]
            if skipped:
                with UI.card().classes("gap-2"):
                    ui.label(f"لم تُستورد ({len(skipped)}): تُعالج يدويًا").classes("font-bold app-text-primary")
                    ui.table(columns=[{"name": k, "label": k, "field": k, "align": "right"}
                                      for k in ("الحالة", "رقم الأمر", "القسم", "الاسم في الورقة",
                                                "الاسم في النظام", "الملف", "الصفحة", "السطر")],
                             rows=skipped, pagination={"rowsPerPage": 20}).classes("w-full")

    def _row(self, i, it):
        rv = self.result.review[it["review_index"]]
        return {"key": i, "status": it["status"], "order": it.get("order_number"),
                "paper": rv["الاسم في الورقة"], "name": it["full_name_ar"],
                "gender": GENDERS.get(it.get("gender"), "ذكر"),
                "average": "" if it.get("average") is None else it["average"],
                "missing": rv.get("يحتاج إكمال", "")}

    def _edit_row(self, row, table):
        it = self.result.items[row["key"]]
        with ui.dialog() as dlg, UI.card().classes("app-dialog gap-3"):
            ui.label("تصحيح قبل الاستيراد").classes("app-section-title")
            ui.label(f"في الورقة: {row['paper']}").classes("app-caption")
            name = UI.text_input("الاسم الذي يُحفظ", value=it["full_name_ar"])
            if it["status"] != soi.NEW:
                name.disable()
                ui.label("طالب موجود: يبقى اسمه المحفوظ. غيّره من صفحة الطالب إن لزم.").classes("app-caption")
            gender = ui.select(GENDERS, value=it.get("gender") or 1, label="الجنس").props("outlined dense")

            def save():
                if it["status"] == soi.NEW:
                    it["full_name_ar"] = " ".join(str(name.value or "").split()) or it["full_name_ar"]
                it["gender"] = int(gender.value or 1)
                new = self._row(row["key"], it)
                table.rows[row["key"]] = new
                table.selected = [new if s["key"] == new["key"] else s for s in table.selected]
                table.update()
                dlg.close()
            with ui.row().classes("app-dialog-actions"):
                UI.ghost_button("إلغاء", on_click=dlg.close)
                UI.primary_button("حفظ", icon="check", on_click=save)
        dlg.open()

    # ── step 3: import ───────────────────────────────────────────────────────
    def confirm_import(self):
        chosen = [self.result.items[r["key"]] for r in (self.table.selected or [])]
        if not chosen:
            UI.notify("لم تحدد أي اسم", type="warning")
            return
        new = sum(1 for it in chosen if it["status"] == soi.NEW)
        UI.confirm_dialog("استيراد الأسماء",
                          f"سيُحفظ {len(chosen)} اسمًا ({new} طالب جديد بقيم افتراضية) ويُربط كل منهم بأمر تخرجه. "
                          "كل أمر يُستورد كاملًا أو لا شيء.", "استيراد",
                          lambda: background_tasks.create(self.do_import(chosen)), danger=False)

    async def do_import(self, chosen):
        from data.repositories.students import StudentRepository
        repo = StudentRepository()
        done, failed, warnings, created, order_ids = 0, [], [], [], {}
        for (order_no, _dept), group in soi.group_by_order(chosen).items():
            try:
                res = await run.io_bound(repo.bulk_import, soi.payloads(group))
                done += len(group)
                warnings += res.get("order_warnings") or []
                created += res.get("created_orders") or []
                order_ids.update({k: (v, _dept) for k, v in (res.get("order_ids") or {}).items()})
            except Exception as err:
                failed.append(f"{order_no or 'بلا رقم'}: {err}")
        with self.container, ui.dialog() as dlg, UI.card().classes("app-dialog gap-2").style("width: 640px"):
            ui.label("نتيجة الاستيراد").classes("app-section-title")
            ui.label(f"حُفظ {done} اسمًا.").classes("text-sm")
            if created:
                ui.label("أوامر أُنشئت: " + "، ".join(created)).classes("text-sm text-positive")
            if order_ids:
                self._attach_scans(order_ids)
            for f in failed:
                ui.label(f"لم يُستورد الأمر {f}").classes("text-sm text-red-600")
            if warnings:
                ui.label("تنبيهات الربط:").classes("font-bold")
                for w in warnings[:30]:
                    ui.label(w).classes("app-caption")
            UI.primary_button("إغلاق", on_click=dlg.close)
        dlg.open()

    def _attach_scans(self, order_ids: dict):
        """Keep the scanned paper with its order (the order's images, as in «أوامر التخرج»)."""
        from services import order_images
        ui.label("حفظ الورقة الممسوحة مع الأمر (للأرشيف):").classes("font-bold")
        last_pdf = None
        if getattr(self, "last_scan", None):
            pdfs = sorted(Path(self.last_scan).glob("*.pdf"))
            last_pdf = pdfs[0] if pdfs else None

        async def attach(order_id, name, data, label):
            try:
                n = await run.io_bound(order_images.upload_file, order_id, name, data)
                UI.notify(f"{label}: حُفظت {n} صفحة", type="positive")
            except Exception as err:
                UI.notify(f"{label}: تعذر الحفظ: {err}", type="negative")

        for order_no, (order_id, _dept) in order_ids.items():
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(f"الأمر {order_no}").classes("text-sm w-32")
                if last_pdf:
                    UI.secondary_button("إرفاق آخر مسح", icon="attach_file",
                                        on_click=lambda oid=order_id, no=order_no: background_tasks.create(
                                            attach(oid, last_pdf.name, last_pdf.read_bytes(), no)))

                async def on_up(e, oid=order_id, no=order_no):
                    name, data = await read_upload(e)
                    await attach(oid, name, data, no)
                clear_when_done(ui.upload(label="أو اختر ملف المسح (PDF أو صورة)", auto_upload=True,
                                          on_upload=on_up).props('accept=".pdf,.jpg,.jpeg,.png" flat bordered dense')
                                .classes("flex-1"))


def scan_card(title: str, hint: str) -> None:
    """The same scanner card for other pages (official ranking lists)."""
    from types import SimpleNamespace
    ScannedOrdersImportScreen._scan_card(SimpleNamespace(), title, hint)
