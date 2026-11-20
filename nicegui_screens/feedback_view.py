# =============================================================================
# nicegui_screens/feedback_view.py — «ملاحظات وشكاوى»
# The user writes a note; the program adds the screen they were on, the version and the
# user. Online only. Admins also see the notes received.
# =============================================================================

from nicegui import ui

from nicegui_ui.ui_components import UI
from data.repositories.base import OfflineModeError
from data.repositories.feedback import FeedbackRepository


def open_feedback_dialog(screen_label: str = "") -> None:
    from nicegui_ui.state import app_session
    repo = FeedbackRepository()

    with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full app-card"):
        with ui.row().classes("w-full items-center"):
            ui.label("ملاحظات وشكاوى").classes("text-lg font-bold app-text-primary")
            ui.space()
            UI.ghost_button("إغلاق", icon="close", on_click=dialog.close)
        ui.label("اكتب المشكلة بالتفصيل (مثلًا: ماذا حاولت أن تفعل وماذا حدث). "
                 "تُحفظ معها الشاشة الحالية وإصدار البرنامج واسم المستخدم.").classes("app-caption")
        box = ui.textarea(label="الملاحظة").props("outlined autogrow counter maxlength=4000").classes("w-full")
        status = ui.label("").classes("app-caption")

        def send():
            text = (box.value or "").strip()
            if not text:
                ui.notify("اكتب الملاحظة أولًا", type="warning")
                return
            try:
                repo.send(text, screen_label, getattr(app_session, "emp_id", None))
            except OfflineModeError:
                ui.notify("لا يمكن إرسال الملاحظة والبرنامج غير متصل بالخادم", type="warning")
                return
            except Exception as exc:
                ui.notify(f"تعذر الإرسال: {exc}", type="negative")
                return
            box.value = ""
            ui.notify("تم إرسال الملاحظة، شكرًا لك", type="positive")
            dialog.close()

        UI.primary_button("إرسال", icon="send", on_click=send)

        if getattr(app_session, "role", "") == "admin":
            ui.separator()
            ui.label("الملاحظات الواردة").classes("font-bold app-text-primary")
            holder = ui.column().classes("w-full gap-2 max-h-[40vh] overflow-y-auto")

            def show():
                holder.clear()
                items = repo.list_all()
                with holder:
                    if not items:
                        ui.label("لا توجد ملاحظات.").classes("app-caption")
                    for it in items:
                        with ui.card().classes("w-full app-card p-3 gap-1"):
                            ui.label(it.get("message") or "").classes("whitespace-pre-wrap")
                            ui.label(f"{it.get('created_at') or ''} — {it.get('user_name') or 'غير معروف'} — "
                                     f"{it.get('screen') or '—'} — الإصدار {it.get('app_version') or '—'}"
                                     ).classes("app-caption")

            show()
    dialog.open()
