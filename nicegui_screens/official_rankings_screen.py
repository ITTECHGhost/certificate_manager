# =============================================================================
# nicegui_screens/official_rankings_screen.py — صفحة «قوائم الترتيب الرسمية»
# A full page (like أوامر التخرج): paginated + searchable lists, the names of one list
# (search, only-unlinked, manual link to a student) and the Excel import. Online only.
# Saving a list is ONE request (header + every entry); the server saves all or nothing.
# =============================================================================

import base64

from nicegui import background_tasks, run, ui

from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import read_upload, clear_when_done
from data.repositories.official_rankings import OfficialRankingRepository, LIST_TYPE_LABELS

STUDY_TYPES = {"morning": "صباحي", "evening": "مسائي", "parallel": "موازي"}
ROUNDS = {"1": "الدور الأول", "2": "الدور الثاني"}
LISTS_PER_PAGE = 25
ENTRIES_PER_PAGE = 50


def scope_text(row: dict) -> str:
    """«صباحي / الدور الأول» for a list that has them, else a dash."""
    parts = (STUDY_TYPES.get(row.get("study_type") or ""), ROUNDS.get(row.get("exam_round") or ""))
    return " / ".join(p for p in parts if p) or "—"


def _me() -> int | None:
    from nicegui_ui.state import app_session
    return getattr(app_session, "emp_id", None)


class OfficialRankingsScreen:
    def __init__(self):
        self.repo = OfficialRankingRepository()
        self.search = ""
        self.page = 1
        self.container = ui.column().classes("w-full gap-4")
        self.show_lists()

    # ── VIEW 1: the lists ────────────────────────────────────────────────────
    def show_lists(self):
        self.container.clear()
        with self.container:
            with UI.card().classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2"):
                    def on_search(e):
                        self.search = str(getattr(e, "value", "") or "").strip()
                        self.page = 1
                        self._lists_view.refresh()

                    UI.search_input(placeholder="ابحث برقم الأمر أو القسم أو العام الدراسي",
                                    on_change=on_search).classes("flex-1 min-w-[220px] max-w-md")
                    ui.space()
                    UI.primary_button("استيراد قائمة من Excel", icon="upload_file", on_click=self.show_import)
                ui.label("ترتيب الطلبة كما ورد في الأمر الرسمي. الوثيقة تأخذ تسلسل الطالب من هنا؛ "
                         "إن لم يوجد الطالب في قائمة يُستعمل التسلسل المحسوب.").classes("app-caption")

                @ui.refreshable
                def lists_view():
                    self._build_lists_table()

                lists_view()
                self._lists_view = lists_view

    def _build_lists_table(self):
        data = self.repo.page(self.search, self.page, LISTS_PER_PAGE)
        total, items = int(data.get("total") or 0), data.get("items") or []
        if not items:
            if self.search:
                UI.empty_state("لا توجد قائمة مطابقة", "غيّر البحث.", icon="search_off")
            else:
                UI.empty_state("لا توجد قوائم بعد", "استورد أول قائمة من ملف Excel (أو البرنامج غير متصل بالخادم).",
                               icon="format_list_numbered", action_text="استيراد قائمة من Excel",
                               on_action=self.show_import)
            return
        rows = [{
            "id": r["id"], "type": LIST_TYPE_LABELS.get(r["list_type"], r["list_type"]),
            "order": f"{r.get('order_number') or '—'} في {r.get('order_date') or '—'}",
            "dept": r.get("department_name") or "كل الأقسام", "scope": scope_text(r),
            "year": r.get("academic_year") or "—",
            "count": f"{r.get('matched', 0)} / {r.get('total', 0)}",
        } for r in items]
        table = UI.data_table([
            {"name": "type", "label": "النوع", "field": "type"},
            {"name": "order", "label": "الأمر", "field": "order"},
            {"name": "dept", "label": "القسم", "field": "dept"},
            {"name": "scope", "label": "الدراسة / الدور", "field": "scope"},
            {"name": "year", "label": "العام", "field": "year"},
            {"name": "count", "label": "مرتبطون / المجموع", "field": "count"},
            {"name": "actions", "label": "", "field": "actions"},
        ], rows, clickable=True)
        table.add_slot("body-cell-actions", """
            <q-td :props="props" auto-width>
              <q-btn flat round dense icon="document_scanner" aria-label="الورقة الممسوحة"
                     @click.stop="$parent.$emit('scan_list', props.row)"><q-tooltip>الورقة الممسوحة</q-tooltip></q-btn>
              <q-btn flat round dense icon="delete" class="app-btn-danger-icon" aria-label="حذف القائمة"
                     @click.stop="$parent.$emit('del_list', props.row)"><q-tooltip>حذف القائمة</q-tooltip></q-btn>
            </q-td>""")
        table.on("rowClick", lambda e: self.show_entries(e.args[1]["id"]))
        table.on("del_list", lambda e: self._confirm_delete(e.args))
        table.on("scan_list", lambda e: self._show_scans(e.args))

        def go(page: int):
            self.page = max(1, int(page))
            self._lists_view.refresh()
        UI.paginator(total, self.page, LISTS_PER_PAGE, go)

    def _confirm_delete(self, row: dict):
        def do():
            try:
                ok = self.repo.delete(row["id"], personnel_id=_me())
            except Exception as err:
                UI.notify(str(err) or "لا يمكن الحذف دون اتصال بالخادم", type="negative")
                return
            if not ok:
                UI.notify("لم تُحذف القائمة (لا تملك الصلاحية أو حدث خطأ)", type="negative")
                return
            UI.notify("حُذفت القائمة", type="positive")
            self._lists_view.refresh()
        UI.confirm_dialog("حذف القائمة", "تُؤرشف القائمة وتختفي من الصفحة. الوثائق الصادرة سابقًا لا تتغير.", "حذف", do)

    def _show_scans(self, row: dict):
        """«الورقة الممسوحة»: upload (image or PDF), view and archive the scanned pages."""
        from services import ranking_images as rimg
        rid = row["id"]
        with ui.dialog() as dialog, ui.card().classes("w-[900px] max-w-full app-card"):
            with ui.row().classes("w-full items-center"):
                ui.label(f"الورقة الممسوحة — {row.get('title') or row.get('scope') or rid}"
                         ).classes("text-lg font-bold app-text-primary")
                ui.space()
                UI.ghost_button("إغلاق", icon="close", on_click=dialog.close)
            big = ui.image().classes("w-full max-h-[60vh]").props("fit=contain")
            thumbs = ui.row().classes("w-full gap-2")

            async def refresh():
                thumbs.clear()
                try:
                    items = await run.io_bound(rimg.list_images, rid)
                except Exception as err:
                    UI.notify(str(err), type="negative")
                    return
                with thumbs:
                    if not items:
                        ui.label("لا توجد صفحات ممسوحة لهذه القائمة.").classes("app-caption")
                    for it in items:
                        await thumb_card(it)

            async def show_big(it):
                data = await run.io_bound(rimg.get_image, rid, it["id"])
                big.set_source("data:image/jpeg;base64," + base64.b64encode(data).decode())

            async def thumb_card(it):
                data = await run.io_bound(rimg.get_image, rid, it["id"], True)
                with ui.column().classes("items-center gap-0"):
                    ui.image("data:image/jpeg;base64," + base64.b64encode(data).decode()).classes(
                        "w-24 h-32 cursor-pointer border").props("fit=contain").on(
                        "click", lambda _e, i=it: show_big(i))
                    with ui.row().classes("items-center gap-1"):
                        ui.label(f"ص {it.get('page_no')}").classes("app-caption")
                        ui.button(icon="delete", on_click=lambda _e, i=it: remove(i)).props(
                            "flat round dense").classes("app-btn-danger-icon")

            def remove(it):
                async def do():
                    try:
                        await run.io_bound(rimg.delete_image, rid, it["id"], _me())
                    except Exception as err:
                        UI.notify(str(err), type="negative")
                        return
                    big.set_source("")
                    UI.notify("أُرشفت الصفحة", type="positive")
                    await refresh()
                UI.confirm_dialog("حذف الصفحة", "تُؤرشف الصفحة وتختفي من القائمة.", "حذف",
                                 lambda: background_tasks.create(do()))

            async def on_upload(e):
                name, data = await read_upload(e)
                try:
                    added = await run.io_bound(rimg.upload_file, rid, name, data, _me())
                except Exception as err:
                    UI.notify(str(err), type="negative")
                    return
                UI.notify(f"أُضيفت {added} صفحة" if added else "الصفحات موجودة مسبقًا", type="positive")
                await refresh()

            clear_when_done(ui.upload(label="رفع صورة أو PDF", auto_upload=True, multiple=True,
                                      on_upload=on_upload).props('accept=".jpg,.jpeg,.png,.pdf" flat bordered'
                                                                 ).classes("w-full"))
            ui.timer(0.1, refresh, once=True)
        dialog.open()

    # ── VIEW 2: names of one list ────────────────────────────────────────────
    def show_entries(self, ranking_id: int):
        self.container.clear()
        state = {"search": "", "only_unlinked": False, "page": 1}
        from data.repositories import StudentRepository
        srepo = StudentRepository()
        with self.container:
            with UI.card().classes("flex-1"):
                with ui.row().classes("w-full items-center gap-2"):
                    UI.ghost_button("رجوع إلى القوائم", icon="arrow_forward", on_click=self.show_lists)

                    def on_search(e):
                        state["search"], state["page"] = str(getattr(e, "value", "") or "").strip(), 1
                        entries_view.refresh()

                    UI.search_input(placeholder="ابحث بالاسم أو التسلسل",
                                    on_change=on_search).classes("flex-1 min-w-[220px] max-w-md")

                    def on_toggle(e):
                        state["only_unlinked"], state["page"] = bool(e.value), 1
                        entries_view.refresh()

                    ui.switch("غير المرتبطين فقط", on_change=on_toggle)
                ui.label("الأسماء غير المرتبطة: اختر الطالب الصحيح ثم اضغط «ربط».").classes("app-caption")

                @ui.refreshable
                def entries_view():
                    data = self.repo.entries_page(ranking_id, state["search"], state["only_unlinked"],
                                                  state["page"], ENTRIES_PER_PAGE)
                    items, total = data.get("items") or [], int(data.get("total") or 0)
                    if not items:
                        UI.empty_state("لا توجد أسماء مطابقة", "غيّر البحث أو أوقف «غير المرتبطين فقط».", icon="search_off")
                        return
                    for e in items:
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label(str(e["position"])).classes("w-10 text-center font-bold")
                            ui.label(e.get("name_written") or "").classes("flex-1")
                            ui.label("" if e.get("average") is None else f"{e['average']:.4f}").classes("w-24")
                            if e.get("student_id"):
                                ui.label(f"✓ {e.get('student_name')}").classes("flex-1 text-positive")
                                UI.ghost_button("فك الربط", icon="link_off",
                                                on_click=lambda _=None, p=e["position"]: set_link(p, None))
                            else:
                                first = (e.get("name_written") or "").split(" ")[0]
                                opts = {s["student_id"]: s.get("name_ar") or "" for s in
                                        (srepo.search_students_paginated(first, 30, 0) or []) if s.get("student_id")}
                                sel = UI.select("اختر الطالب", opts, with_input=True).classes("flex-1")
                                UI.ghost_button("ربط", icon="link",
                                                on_click=lambda _=None, p=e["position"], sel=sel: set_link(p, sel.value))

                    def go(page: int):
                        state["page"] = max(1, int(page))
                        entries_view.refresh()
                    UI.paginator(total, state["page"], ENTRIES_PER_PAGE, go)

                def set_link(position: int, student_id):
                    try:
                        ok = self.repo.set_student(ranking_id, position, student_id, personnel_id=_me())
                    except Exception as err:
                        UI.notify(str(err) or "لا يمكن الربط دون اتصال بالخادم", type="negative")
                        return
                    if not ok:
                        UI.notify("لم يُحفظ الربط (لا تملك الصلاحية أو حدث خطأ)", type="negative")
                        return
                    entries_view.refresh()

                entries_view()

    # ── VIEW 3: import ───────────────────────────────────────────────────────
    def show_import(self):
        self.container.clear()
        with self.container:
            from nicegui_screens.scanned_orders_import_screen import scan_card
            scan_card("مسح ورقة القائمة بالماسح",
                      "ضع أوراق القائمة (الصفحة الأولى أولًا) ثم اضغط «مسح». أعطِ الملف للذكاء الاصطناعي ليُخرج "
                      "ملف CSV بالأعمدة نفسها، ثم ارفعه أدناه.")
        state = {"rows": []}
        try:
            from data.repositories import DepartmentRepository
            depts = {d["id"]: d.get("name_ar") or "" for d in DepartmentRepository().get_all() or []}
        except Exception:
            depts = {}
        with self.container:
            with UI.card().classes("flex-1"):
                UI.ghost_button("رجوع إلى القوائم", icon="arrow_forward", on_click=self.show_lists)
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    list_type = UI.select("نوع القائمة", LIST_TYPE_LABELS, value="jobs").classes("w-44")
                    dept = UI.select("القسم", depts).classes("w-56")
                    stype = UI.select("الدراسة", STUDY_TYPES).props("clearable").classes("w-36")
                    rnd = UI.select("الدور", ROUNDS).props("clearable").classes("w-36")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    order_no = UI.text_input("رقم الأمر").classes("w-44")
                    order_date = UI.date_input("تاريخ الأمر").classes("w-44")
                    year = UI.text_input("العام الدراسي", placeholder="2025/2026").classes("w-44")
                ui.label("للتعيين: القسم + الدراسة + الدور. للدراسات العليا: القسم فقط (اترك الدراسة والدور فارغين).") \
                    .classes("app-caption")
                preview = ui.column().classes("w-full gap-1")

                async def on_upload(e):
                    from services.official_ranking_import import read_list_file
                    try:
                        name, content = await read_upload(e)
                        rows = read_list_file(name, content)
                        ids = await run.io_bound(self.repo.match, [r["name_written"] for r in rows], dept.value)
                    except Exception as err:
                        UI.notify(f"تعذرت قراءة القائمة: {err}", type="negative")
                        return
                    for r, sid in zip(rows, ids):
                        r["student_id"] = sid
                    state["rows"] = rows
                    preview.clear()
                    matched = sum(1 for r in rows if r["student_id"])
                    with preview:
                        ui.label(f"{len(rows)} اسمًا — طابق منها {matched}؛ الباقي تربطه بعد الحفظ.").classes("font-bold")
                        for r in rows[:300]:
                            avg = "" if r["average"] is None else f"  {r['average']}"
                            ui.label(f"{'✓' if r['student_id'] else '—'}  {r['position']}. {r['name_written']}{avg}").classes(
                                "text-sm " + ("text-positive" if r["student_id"] else "app-text-muted"))
                        if len(rows) > 300:
                            ui.label(f"… و{len(rows) - 300} اسمًا آخر (تُحفظ كلها).").classes("app-caption")

                clear_when_done(ui.upload(label="اسحب ملف القائمة هنا (Excel أو CSV)", auto_upload=True, on_upload=on_upload)) \
                    .props('accept=".xlsx,.csv"').classes("w-full")

                async def save():
                    if not state["rows"]:
                        UI.notify("ارفع ملف القائمة أولاً", type="warning")
                        return
                    if not dept.value:
                        UI.notify("اختر القسم", type="warning")
                        return
                    jobs = list_type.value == "jobs"
                    if jobs and not (stype.value and rnd.value):
                        UI.notify("قائمة التعيين تحتاج الدراسة والدور", type="warning")
                        return
                    header = {"list_type": list_type.value, "department_id": dept.value,
                              "study_type": stype.value if jobs else None, "exam_round": rnd.value if jobs else None,
                              "order_number": (order_no.value or "").strip(),
                              "order_date": (order_date.value or "").strip() or None,
                              "academic_year": (year.value or "").strip(), "created_by": _me(),
                              "title": f"{LIST_TYPE_LABELS[list_type.value]} — {depts.get(dept.value, '')}"}
                    entries = [{k: r[k] for k in ("position", "name_written", "average", "student_id")} for r in state["rows"]]
                    try:
                        rid = await run.io_bound(self.repo.save, header, entries)
                    except Exception as err:
                        UI.notify(str(err), type="negative")
                        return
                    UI.notify("حُفظت القائمة", type="positive")
                    self.show_entries(rid)

                UI.primary_button("حفظ القائمة", icon="save", on_click=save)
