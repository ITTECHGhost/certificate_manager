# =============================================================================
# nicegui_screens/feedback_view.py — «ملاحظات وشكاوى»
# The user writes a note; the program adds the screen they were on, the version and the
# user. Online only. Admins also see the notes received.
# =============================================================================

import base64

from nicegui import ui

from nicegui_ui.ui_components import UI
from data.repositories.base import OfflineModeError
from data.repositories.feedback import FeedbackRepository


def open_feedback_dialog(screen_label: str = "", screenshot: bytes | None = None, on_open_notes=None) -> None:
    """screenshot: a picture of the screen taken just before the dialog opened (optional)."""
    from nicegui_ui.state import app_session
    from nicegui_ui.upload_utils import read_upload, clear_when_done
    repo = FeedbackRepository()
    pictures: list = []   # (name, bytes) chosen by the user

    with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full app-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("ملاحظات وشكاوى").classes("text-lg font-bold app-text-primary")
            ui.space()
            UI.ghost_button("إغلاق", icon="close", on_click=dialog.close)
        ui.label("اكتب المشكلة بالتفصيل (مثلًا: ماذا حاولت أن تفعل وماذا حدث). "
                 "تُحفظ معها الشاشة الحالية وإصدار البرنامج واسم المستخدم.").classes("app-caption")
        box = ui.textarea(label="الملاحظة").props("outlined autogrow counter maxlength=4000").classes("w-full")
        shot_cb = None
        if screenshot:
            with ui.row().classes("w-full items-center gap-2"):
                shot_cb = ui.checkbox("إرفاق لقطة الشاشة الحالية", value=True)
                img = ui.image("data:image/png;base64," + base64.b64encode(screenshot).decode()) \
                    .classes("w-40 rounded border cursor-pointer")
                img.on("click", lambda: _big(screenshot, "image/png"))
        pics_lbl = ui.label("").classes("app-caption")

        async def on_pic(e):
            name, data = await read_upload(e)
            pictures.append((name, data))
            pics_lbl.set_text("صور مرفقة: " + "، ".join(n for n, _ in pictures))
        clear_when_done(ui.upload(label="إرفاق صور (يمكن اختيار عدة صور)", multiple=True, auto_upload=True,
                                  on_upload=on_pic).props('accept=".png,.jpg,.jpeg" flat bordered dense')
                        .classes("w-full"))
        log_cb = ui.checkbox("إرفاق سجل البرنامج (يساعد قسم IT على معرفة السبب)", value=True)
        status = ui.label("").classes("app-caption")

        def send():
            text = (box.value or "").strip()
            if not text:
                ui.notify("اكتب الملاحظة أولًا", type="warning")
                return
            uid = getattr(app_session, "emp_id", None)
            # The raw errors behind the last toasts, so IT sees the real cause, not only the friendly text
            from utils.error_formatter import recent_errors
            if recent_errors:
                text += "\n\n--- آخر الأخطاء (تقنية) ---\n" + "\n".join(recent_errors)
            try:
                fid = repo.send(text, screen_label, uid)
            except OfflineModeError:
                ui.notify("لا يمكن إرسال الملاحظة والبرنامج غير متصل بالخادم", type="warning")
                return
            except Exception as exc:
                ui.notify(f"تعذر الإرسال: {exc}", type="negative")
                return
            to_send = list(pictures)
            if shot_cb is not None and shot_cb.value:
                to_send.insert(0, ("لقطة الشاشة.png", screenshot))
            failed = 0
            for name, data in to_send:
                try:
                    repo.add_image(fid, uid, name, data)
                except Exception:
                    failed += 1
            if log_cb.value:
                try:
                    repo.add_log(fid, uid)
                except Exception:
                    failed += 1
            box.value = ""
            if failed:
                ui.notify(f"أُرسلت الملاحظة، لكن تعذر رفع {failed} مرفق", type="warning")
            ui.notify("تم إرسال الملاحظة، شكرًا لك", type="positive")
            dialog.close()

        UI.primary_button("إرسال", icon="send", on_click=send)


        if on_open_notes is not None:
            def _go():
                dialog.close()
                on_open_notes()
            UI.ghost_button("عرض الملاحظات السابقة", icon="list_alt", on_click=_go)
    dialog.open()


PAGE_SIZE = 20


def build_notes_panel() -> None:
    """The notes list: admins see every note, other users their own (the server decides).
    Filter by status, search the text, 20 per page. Used by the «الملاحظات» screen."""
    from nicegui_ui.state import app_session
    repo = FeedbackRepository()
    user_id = getattr(app_session, "emp_id", None)
    is_admin = getattr(app_session, "role", "") == "admin"
    state = {"items": [], "page": 0}

    with ui.row().classes("w-full items-center flex-wrap gap-2"):
        ui.label("الملاحظات الواردة" if is_admin else "ملاحظاتي").classes("font-bold app-text-primary")
        ui.space()
        status_sel = ui.select({"": "كل الحالات", **STATUS_AR}, value="", label="الحالة")             .props("outlined dense").classes("w-40")
        search = ui.input(label="بحث في النص").props("outlined dense clearable").classes("w-64")
        UI.ghost_button("تحديث", icon="refresh", on_click=lambda: show())
    holder = ui.column().classes("w-full gap-2")
    pager = ui.row().classes("w-full items-center justify-center gap-2")

    def run(action, ok_msg):
        try:
            action()
        except OfflineModeError:
            ui.notify("البرنامج غير متصل بالخادم", type="warning")
            return
        except Exception as exc:
            ui.notify(str(exc), type="negative")
            return
        ui.notify(ok_msg, type="positive")
        show()

    def note_card(it):
        fid, status = it.get("id"), it.get("status") or "new"
        with ui.card().classes("w-full app-card p-3 gap-1"):
            with ui.row().classes("w-full items-center flex-wrap gap-x-2 gap-y-0"):
                ui.badge(STATUS_AR.get(status, status)).props(f"color={STATUS_COLOR.get(status, 'grey')}")
                ui.label(f"{it.get('created_at') or ''} — {it.get('user_name') or 'غير معروف'} — "
                         f"{it.get('screen') or '—'} — الإصدار {it.get('app_version') or '—'}"
                         ).classes("app-caption min-w-0 break-words")
            text = ui.label(it.get("message") or "").classes("w-full whitespace-pre-wrap break-words")
            pics_row = ui.row().classes("gap-2")

            def load_pics(f=fid, row=pics_row, btn=None):
                row.clear()
                with row:
                    for im in repo.list_images(f, user_id):
                        try:
                            data = repo.get_image(f, im["id"], user_id)
                        except Exception:
                            continue
                        if data[:2] == b"\x1f\x8b":   # the user's program log, gzipped
                            UI.ghost_button("عرض سجل البرنامج", icon="description",
                                            on_click=lambda d=data: _show_log(d))
                            continue
                        pic = ui.image("data:image/jpeg;base64," + base64.b64encode(data).decode()) \
                            .classes("w-32 rounded border cursor-pointer")
                        pic.on("click", lambda d=data: _big(d, "image/jpeg"))
            with pics_row:
                UI.ghost_button("عرض الصور المرفقة", icon="image", on_click=lambda: load_pics())
            if it.get("reply"):
                with ui.column().classes("w-full gap-0 p-2 rounded bg-green-50"):
                    ui.label(it["reply"]).classes("whitespace-pre-wrap")
                    ui.label(f"الرد: {it.get('replied_by_name') or ''} — {it.get('replied_at') or ''}"
                             ).classes("app-caption")
            if is_admin:
                rbox = ui.textarea(label="الرد", value=it.get("reply") or "").props(
                    "outlined autogrow dense maxlength=4000").classes("w-full")
                with ui.row().classes("w-full items-center flex-wrap gap-2"):
                    sel = ui.select(STATUS_AR, value=status, label="الحالة").props("outlined dense").classes("w-40")
                    UI.primary_button("حفظ الرد", icon="reply", on_click=lambda f=fid, r=rbox, s=sel: run(
                        lambda: repo.reply(f, user_id, (r.value or "").strip(), s.value), "حُفظ الرد"))
                    UI.ghost_button("حذف", icon="delete", on_click=lambda f=fid: run(
                        lambda: repo.delete(f, user_id), "حُذفت الملاحظة"))
            elif status == "new" and it.get("created_by") == user_id:
                def start_edit(lbl=text, f=fid, row_holder=None):
                    lbl.set_visibility(False)
                    with lbl.parent_slot.parent:
                        ebox = ui.textarea(value=lbl.text).props("outlined autogrow dense maxlength=4000"
                                                                 ).classes("w-full")
                        UI.primary_button("حفظ التعديل", icon="save", on_click=lambda: run(
                            lambda: repo.edit(f, user_id, (ebox.value or "").strip()), "حُفظ التعديل"))
                with ui.row().classes("gap-2"):
                    UI.ghost_button("تعديل", icon="edit", on_click=lambda: start_edit())
                    UI.ghost_button("حذف", icon="delete", on_click=lambda f=fid: run(
                        lambda: repo.delete(f, user_id), "حُذفت الملاحظة"))


    def filtered():
        st, q = status_sel.value or "", (search.value or "").strip().lower()
        return [it for it in state["items"]
                if (not st or (it.get("status") or "new") == st)
                and (not q or q in " ".join(str(it.get(k) or "") for k in
                                            ("message", "reply", "user_name", "screen")).lower())]

    def render():
        items = filtered()
        pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
        state["page"] = min(state["page"], pages - 1)
        holder.clear()
        with holder:
            if not items:
                ui.label("لا توجد ملاحظات.").classes("app-caption")
            start = state["page"] * PAGE_SIZE
            for it in items[start:start + PAGE_SIZE]:
                note_card(it)
        pager.clear()
        if pages > 1:
            with pager:
                def go(d):
                    state["page"] += d
                    render()
                UI.ghost_button("السابق", icon="chevron_right", on_click=lambda: go(-1)).set_enabled(state["page"] > 0)
                ui.label(f"صفحة {state['page'] + 1} من {pages} ({len(items)} ملاحظة)").classes("app-caption")
                UI.ghost_button("التالي", icon="chevron_left", on_click=lambda: go(1)).set_enabled(state["page"] < pages - 1)

    def show():
        state["items"] = repo.list_all(user_id)
        render()

    def _refilter(_=None):
        state["page"] = 0
        render()
    status_sel.on_value_change(_refilter)
    search.on_value_change(_refilter)
    show()



STATUS_AR = {"new": "جديدة", "in_progress": "قيد المعالجة", "done": "تمت"}
STATUS_COLOR = {"new": "orange", "in_progress": "blue", "done": "green"}


def _show_log(data: bytes) -> None:
    """The log a user attached: newest lines last, left-to-right, copyable."""
    import gzip
    try:
        text = gzip.decompress(data).decode("utf-8", errors="replace")
    except Exception:
        text = "(تعذر فتح السجل)"
    with ui.dialog() as d, ui.card().classes("w-[95vw] max-w-[1200px] app-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("سجل البرنامج").classes("font-bold app-text-primary")
            ui.space()
            UI.ghost_button("إغلاق", icon="close", on_click=d.close)
        ui.code(text, language="text").classes("w-full max-h-[75vh] overflow-auto").style("direction:ltr")
    d.open()


def _big(data: bytes, mime: str) -> None:
    """One picture, large."""
    with ui.dialog() as d, ui.card().classes("max-w-[95vw] app-card"):
        ui.image(f"data:{mime};base64," + base64.b64encode(data).decode()).classes("w-[85vw] max-w-[1400px]")
        UI.ghost_button("إغلاق", icon="close", on_click=d.close)
    d.open()
