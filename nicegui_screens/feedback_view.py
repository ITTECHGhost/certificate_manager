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


def open_feedback_dialog(screen_label: str = "", screenshot: bytes | None = None) -> None:
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
        status = ui.label("").classes("app-caption")

        def send():
            text = (box.value or "").strip()
            if not text:
                ui.notify("اكتب الملاحظة أولًا", type="warning")
                return
            uid = getattr(app_session, "emp_id", None)
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
            box.value = ""
            if failed:
                ui.notify(f"أُرسلت الملاحظة، لكن تعذر رفع {failed} صورة", type="warning")
            ui.notify("تم إرسال الملاحظة، شكرًا لك", type="positive")
            dialog.close()

        UI.primary_button("إرسال", icon="send", on_click=send)

        user_id = getattr(app_session, "emp_id", None)
        is_admin = getattr(app_session, "role", "") == "admin"
        ui.separator()
        ui.label("الملاحظات الواردة" if is_admin else "ملاحظاتي").classes("font-bold app-text-primary")
        holder = ui.column().classes("w-full gap-2 max-h-[45vh] overflow-y-auto")

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
                with ui.row().classes("w-full items-center"):
                    ui.badge(STATUS_AR.get(status, status)).props(f"color={STATUS_COLOR.get(status, 'grey')}")
                    ui.space()
                    ui.label(f"{it.get('created_at') or ''} — {it.get('user_name') or 'غير معروف'} — "
                             f"{it.get('screen') or '—'} — الإصدار {it.get('app_version') or '—'}"
                             ).classes("app-caption")
                text = ui.label(it.get("message") or "").classes("whitespace-pre-wrap")
                pics_row = ui.row().classes("gap-2")

                def load_pics(f=fid, row=pics_row, btn=None):
                    row.clear()
                    with row:
                        for im in repo.list_images(f, user_id):
                            try:
                                data = repo.get_image(f, im["id"], user_id)
                            except Exception:
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
                    with ui.row().classes("w-full items-end gap-2"):
                        rbox = ui.textarea(label="الرد", value=it.get("reply") or "").props(
                            "outlined autogrow dense maxlength=4000").classes("flex-1")
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

        def show():
            holder.clear()
            items = repo.list_all(user_id)
            with holder:
                if not items:
                    ui.label("لا توجد ملاحظات.").classes("app-caption")
                for it in items:
                    note_card(it)

        show()
    dialog.open()


STATUS_AR = {"new": "جديدة", "in_progress": "قيد المعالجة", "done": "تمت"}
STATUS_COLOR = {"new": "orange", "in_progress": "blue", "done": "green"}


def _big(data: bytes, mime: str) -> None:
    """One picture, large."""
    with ui.dialog() as d, ui.card().classes("max-w-[95vw] app-card"):
        ui.image(f"data:{mime};base64," + base64.b64encode(data).decode()).classes("w-[85vw] max-w-[1400px]")
        UI.ghost_button("إغلاق", icon="close", on_click=d.close)
    d.open()
