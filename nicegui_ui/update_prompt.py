# =============================================================================
# nicegui_ui/update_prompt.py — "a new version is available": now, at the next start, or later
# Used at start (once per run of the program) and by Settings → التحقق من التحديثات.
# =============================================================================

import asyncio
import os

from nicegui import run, ui

from nicegui_ui.ui_components import UI

_asked_this_run = False


async def check_at_start() -> None:
    """Once per run: if the server offers a newer client, ask when to install it."""
    global _asked_this_run
    if _asked_this_run:
        return
    _asked_this_run = True
    try:
        from sync_engine import is_online
        import services.updater as upd
        if not is_online():
            return
        res = await run.io_bound(upd.check_for_updates)
        if not res or not res.get("has_update"):
            return
        staged = await run.io_bound(upd.staged_update)
        if staged and staged.get("version") == res.get("latest_version"):
            ui.notify(f"التحديث {res['latest_version']} جاهز وسيُثبَّت عند إعادة تشغيل البرنامج", type="info")
            return
        show_update_dialog(res)
    except Exception:
        pass  # an update check must never disturb the program


def show_update_dialog(res: dict) -> None:
    import services.updater as upd

    with ui.dialog() as dlg, UI.card().classes("w-[520px] max-w-full gap-3"):
        UI.card_header(f"تحديث جديد متاح: {res['latest_version']}", "system_update")
        ui.label(f"الإصدار الحالي: {res['current_version']} ← الجديد: {res['latest_version']}").classes("text-sm font-bold")
        if res.get("changelog_ar"):
            ui.label(res["changelog_ar"]).classes("app-caption whitespace-pre-wrap")
        UI.muted_label("«عند إعادة التشغيل» ينزّل التحديث الآن ويثبّته في المرة القادمة التي يُفتح فيها البرنامج.")

        async def _download():
            n = ui.notification("جاري تنزيل التحديث...", timeout=None, spinner=True)
            path = await run.io_bound(upd.download_patch, res)
            n.dismiss()
            if not path:
                ui.notify("فشل تنزيل ملف التحديث", type="negative")
            return path

        async def _now():
            dlg.close()
            path = await _download()
            if not path:
                return
            ui.notify("تم تنزيل التحديث. جاري إعادة تشغيل البرنامج...", type="positive")
            await asyncio.sleep(1.0)
            if upd.apply_patch_and_restart(path):
                os._exit(0)
            ui.notify("تعذر بدء التثبيت", type="negative")

        async def _at_restart():
            dlg.close()
            path = await _download()
            if path and await run.io_bound(upd.stage_update, res, path):
                ui.notify("سيُثبَّت التحديث عند إعادة تشغيل البرنامج", type="positive")

        with ui.row().classes("app-dialog-actions"):
            UI.ghost_button("لاحقاً", on_click=dlg.close)
            UI.ghost_button("عند إعادة التشغيل", on_click=_at_restart)
            UI.primary_button("تحديث الآن", icon="system_update", on_click=_now)
    dlg.open()
