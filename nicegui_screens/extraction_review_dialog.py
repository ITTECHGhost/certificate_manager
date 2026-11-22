# =============================================================================
# nicegui_screens/extraction_review_dialog.py — «مراجعة الاستخراج»
# The source image (optional, kept in memory only) beside an editable grades table.
# Suspicious rows are coloured (rules in services/extraction_review.py). «اعتماد»
# hands the edited rows back; the caller saves them with the existing single-request
# bulk import (one transaction). Nothing is sent to the server from here.
# =============================================================================
from __future__ import annotations

import base64
from typing import Any, Callable, Dict, List, Optional

from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import clear_when_done, read_upload
from services.extraction_review import flag_rows, set_meta, set_score

ROUND_OPTIONS = {1: "الدور الأول", 2: "الدور الثاني", 3: "الدور الثالث"}
STATUS_OPTIONS = {"PASSED": "ناجح", "FAILED_REPEAT": "راسب (إعادة)",
                  "CARRIED_OVER": "إكمال / عبور", "DEFERRED": "تأجيل"}


def _data_url(name: str, content: bytes) -> str:
    mime = "image/png" if name.lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def open_extraction_review(grades: List[Dict[str, Any]], courses: List[Dict[str, Any]],
                           known_names: Optional[List[str]],
                           on_confirm: Callable[[List[Dict[str, Any]]], None]) -> None:
    """Open the review dialog on a copy of `grades`; `on_confirm(edited_rows)` on «اعتماد»."""
    rows: List[Dict[str, Any]] = [dict(g) for g in grades]
    state = {"image": None, "zoom": 100}
    table_box = {"c": None}
    image_box = {"c": None}

    def render_image():
        c = image_box["c"]
        c.clear()
        with c:
            if state["image"]:
                ui.image(state["image"]).props("fit=contain").style(f"width:{state['zoom']}%")
            else:
                ui.label("لم تُرفع صورة بعد. اختر صورة الأمر أو الكشف لتظهر هنا بجانب الجدول.").classes(
                    "text-sm app-text-muted")

    async def on_image(event):
        name, content = await read_upload(event)
        state["image"] = _data_url(name, content)
        render_image()

    def zoom(delta: int):
        state["zoom"] = max(50, min(300, state["zoom"] + delta))
        render_image()

    def edit_score(i: int, course_id: int, raw):
        text = str(raw if raw is not None else "").strip()
        try:
            value = float(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))) if text else None
        except ValueError:
            ui.notify("الدرجة يجب أن تكون رقمًا.", type="warning")
            return
        rows[i] = set_score(rows[i], course_id, value, courses)
        render_table()

    def edit_meta(i: int, **kw):
        rows[i] = set_meta(rows[i], **kw)
        render_table()

    def render_table():
        c = table_box["c"]
        c.clear()
        flags = flag_rows(rows, courses, known_names)
        bad = sum(1 for f in flags if f)
        with c:
            ui.label(f"{len(rows)} طالب — {bad} صف مشكوك فيه").classes(
                "text-sm font-bold " + ("text-amber-500" if bad else "text-emerald-500"))
            with ui.scroll_area().classes("w-full h-[60vh]"):
                for i, row in enumerate(rows):
                    why = flags[i]
                    tint = "background:rgba(245,158,11,.15);border-color:#f59e0b" if why else ""
                    with ui.column().classes("w-full gap-1 p-2 rounded-xl border border-[var(--border-default)] mb-2").style(tint):
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.input(value=row.get("student_name", "")).props("dense outlined").classes(
                                "flex-1").on("change", lambda e, i=i: edit_meta(i, student_name=e.sender.value))
                            ui.select(ROUND_OPTIONS, value=int(row.get("passed_round") or 1),
                                      on_change=lambda e, i=i: edit_meta(i, passed_round=e.value)).props("dense outlined")
                            ui.select(STATUS_OPTIONS, value=row.get("result_status") or "PASSED",
                                      on_change=lambda e, i=i: edit_meta(i, result_status=e.value)).props("dense outlined")
                            ui.label(f"المعدل: {float(row.get('average') or 0):.3f}").classes("font-bold text-sm")
                        if why:
                            ui.label("⚠ " + "، ".join(why)).classes("text-xs text-amber-600")
                        by_course = {int(s["course_id"]): s["score"] for s in row.get("scores", [])}
                        with ui.row().classes("w-full gap-2 flex-wrap"):
                            for crs in courses:
                                cid = int(crs["id"])
                                cur = by_course.get(cid)
                                ui.input(label=str(crs.get("name_ar") or crs.get("name_en") or cid),
                                         value="" if cur is None else f"{cur:g}",
                                         on_change=None).props("dense outlined").classes("w-28").on(
                                    "change", lambda e, i=i, cid=cid: edit_score(i, cid, e.sender.value))

    def confirm():
        flags = flag_rows(rows, courses, known_names)
        bad = sum(1 for f in flags if f)
        on_confirm(rows)
        ui.notify("تم اعتماد المراجعة" + (f" ({bad} صف ما زال مشكوكًا فيه)" if bad else ""),
                  type="warning" if bad else "positive")
        dlg.close()

    with ui.dialog().props("maximized") as dlg, UI.card().classes("w-full h-full p-4 gap-3 bg-[var(--surface-card)]"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("مراجعة الاستخراج").classes("text-lg font-bold app-text-primary")
            ui.button(icon="close", on_click=dlg.close).props("flat dense round")
        with ui.row().classes("w-full flex-nowrap gap-4 items-start"):
            with ui.column().classes("w-1/2 gap-2"):
                with ui.row().classes("items-center gap-2"):
                    clear_when_done(ui.upload(label="صورة المصدر (اختياري)", auto_upload=True, max_files=1,
                                              on_upload=on_image)).props('accept="image/*" flat bordered')
                    ui.button(icon="zoom_in", on_click=lambda: zoom(25)).props("flat dense round")
                    ui.button(icon="zoom_out", on_click=lambda: zoom(-25)).props("flat dense round")
                with ui.scroll_area().classes("w-full h-[65vh] border border-[var(--border-default)] rounded-xl p-2"):
                    image_box["c"] = ui.column().classes("w-full")
            table_box["c"] = ui.column().classes("w-1/2 gap-2")
        with ui.row().classes("w-full justify-end gap-2"):
            UI.secondary_button("إلغاء", on_click=dlg.close).classes("text-xs px-4 py-1.5")
            UI.primary_button("اعتماد المراجعة", icon="check", on_click=confirm).classes("text-xs px-4 py-1.5")
    render_image()
    render_table()
    dlg.open()
