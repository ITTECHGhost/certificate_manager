# =============================================================================
# nicegui_screens/official_rankings_view.py — «قوائم الترتيب الرسمية»
# Import the ranking list that comes with a college order (Excel), check which names
# matched a student, link the rest by hand, and keep it as the source of the rank
# printed on certificates. Online only (the lists live on the server).
# =============================================================================

from nicegui import run, ui

from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import read_upload, clear_when_done
from data.repositories.official_rankings import OfficialRankingRepository, LIST_TYPE_LABELS

STUDY_TYPES = {"morning": "صباحي", "evening": "مسائي", "parallel": "موازي"}
ROUNDS = {"1": "الدور الأول", "2": "الدور الثاني"}


def open_official_rankings_dialog() -> None:
    repo = OfficialRankingRepository()
    try:
        from data.repositories import DepartmentRepository
        depts = {d["id"]: d.get("name_ar") or "" for d in DepartmentRepository().get_all() or []}
    except Exception:
        depts = {}

    with ui.dialog() as dialog, ui.card().classes("w-[960px] max-w-full app-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("قوائم الترتيب الرسمية").classes("text-lg font-bold app-text-primary")
            ui.space()
            UI.ghost_button("إغلاق", icon="close", on_click=dialog.close)
        ui.label("ترتيب الطلبة كما ورد في الأمر الرسمي. الوثيقة تأخذ تسلسل الطالب من هنا؛ "
                 "إن لم يوجد الطالب في قائمة يُستعمل التسلسل المحسوب.").classes("app-caption")
        body = ui.column().classes("w-full gap-3")

    def show_lists():
        body.clear()
        lists = repo.list_all()
        with body:
            UI.primary_button("استيراد قائمة من Excel", icon="upload_file", on_click=show_import)
            if not lists:
                ui.label("لا توجد قوائم بعد (أو البرنامج غير متصل بالخادم).").classes("app-caption")
                return
            rows = [{
                "id": r["id"], "type": LIST_TYPE_LABELS.get(r["list_type"], r["list_type"]),
                "order": f"{r.get('order_number') or '—'} في {r.get('order_date') or '—'}",
                "dept": r.get("department_name") or "كل الأقسام",
                "scope": " / ".join(x for x in (STUDY_TYPES.get(r.get("study_type") or ""), ROUNDS.get(r.get("exam_round") or "")) if x) or "—",
                "year": r.get("academic_year") or "",
                "count": f"{r.get('matched', 0)} / {r.get('total', 0)}",
            } for r in lists]
            cols = [{"name": "type", "label": "النوع", "field": "type"},
                    {"name": "order", "label": "الأمر", "field": "order"},
                    {"name": "dept", "label": "القسم", "field": "dept"},
                    {"name": "scope", "label": "الدراسة / الدور", "field": "scope"},
                    {"name": "year", "label": "العام", "field": "year"},
                    {"name": "count", "label": "مرتبطون / المجموع", "field": "count"},
                    {"name": "actions", "label": "", "field": "id"}]
            table = ui.table(columns=cols, rows=rows, row_key="id").classes("w-full")
            table.add_slot("body-cell-actions", """
                <q-td :props="props">
                  <q-btn flat dense icon="link" @click="$parent.$emit('open_list', props.row)"><q-tooltip>ربط الأسماء</q-tooltip></q-btn>
                  <q-btn flat dense icon="delete" color="negative" @click="$parent.$emit('del_list', props.row)"><q-tooltip>حذف القائمة</q-tooltip></q-btn>
                </q-td>""")
            table.on("open_list", lambda e: show_entries(e.args["id"]))
            table.on("del_list", lambda e: UI.confirm_dialog(
                "حذف القائمة", "تُحذف القائمة وكل أسمائها. الوثائق الصادرة سابقًا لا تتغير.", "حذف",
                lambda: (repo.delete(e.args["id"]), show_lists())))

    def show_entries(ranking_id: int):
        body.clear()
        entries = repo.entries(ranking_id)
        with body:
            UI.ghost_button("رجوع إلى القوائم", icon="arrow_forward", on_click=show_lists)
            ui.label("الأسماء غير المرتبطة: اختر الطالب الصحيح من القائمة.").classes("app-caption")
            from data.repositories import StudentRepository
            srepo = StudentRepository()
            for e in entries:
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(str(e["position"])).classes("w-10 text-center")
                    ui.label(e.get("name_written") or "").classes("flex-1")
                    ui.label("" if e.get("average") is None else f"{e['average']:.4f}").classes("w-24")
                    if e.get("student_id"):
                        ui.label(f"✓ {e.get('student_name')}").classes("flex-1 text-positive")
                    else:
                        opts = {s["student_id"]: s.get("name_ar") or "" for s in
                                (srepo.search_students_paginated((e.get("name_written") or "").split(" ")[0], 30, 0) or [])
                                if s.get("student_id")}
                        sel = UI.select("اختر الطالب", opts, with_input=True).classes("flex-1")

                        def link(_=None, pos=e["position"], sel=sel):
                            if sel.value and repo.set_student(ranking_id, pos, sel.value):
                                show_entries(ranking_id)
                        UI.ghost_button("ربط", icon="link", on_click=link)

    def show_import():
        body.clear()
        state = {"rows": []}
        with body:
            UI.ghost_button("رجوع إلى القوائم", icon="arrow_forward", on_click=show_lists)
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
                from services.official_ranking_import import read_excel
                try:
                    _name, content = await read_upload(e)
                    rows = read_excel(content)
                    ids = await run.io_bound(repo.match, [r["name_written"] for r in rows], dept.value)
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
                        mark = "✓" if r["student_id"] else "—"
                        avg = "" if r["average"] is None else f"  {r['average']}"
                        ui.label(f"{mark}  {r['position']}. {r['name_written']}{avg}").classes(
                            "text-sm " + ("text-positive" if r["student_id"] else "app-text-muted"))

            clear_when_done(ui.upload(label="اسحب ملف Excel للقائمة هنا (xlsx)", auto_upload=True, on_upload=on_upload)) \
                .props('accept=".xlsx"').classes("w-full")

            async def save():
                if not state["rows"]:
                    UI.notify("ارفع ملف القائمة أولاً", type="warning")
                    return
                if not dept.value:
                    UI.notify("اختر القسم", type="warning")
                    return
                from nicegui_ui.state import app_session
                header = {"list_type": list_type.value, "department_id": dept.value,
                          "study_type": stype.value if list_type.value == "jobs" else None,
                          "exam_round": rnd.value if list_type.value == "jobs" else None,
                          "order_number": (order_no.value or "").strip(), "order_date": (order_date.value or "").strip() or None,
                          "academic_year": (year.value or "").strip(), "created_by": getattr(app_session, "emp_id", None),
                          "title": f"{LIST_TYPE_LABELS[list_type.value]} — {depts.get(dept.value, '')}"}
                entries = [{k: r[k] for k in ("position", "name_written", "average", "student_id")} for r in state["rows"]]
                try:
                    rid = await run.io_bound(repo.save, header, entries)
                except Exception as err:
                    UI.notify(str(err), type="negative")
                    return
                UI.notify("حُفظت القائمة", type="positive")
                show_entries(rid)

            UI.primary_button("حفظ القائمة", icon="save", on_click=save)

    show_lists()
    dialog.open()
