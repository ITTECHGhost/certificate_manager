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
            # The offer dialog is closed by now: show the bar in its own small dialog.
            from nicegui_ui.transfer_progress import TransferProgress
            with ui.dialog().props("persistent") as pdlg, UI.card().classes("w-[460px] max-w-full gap-2"):
                UI.card_header(f"تنزيل التحديث {res['latest_version']}", "download")
                bar = TransferProgress("تنزيل ملف التحديث من الخادم", done_text="اكتمل التنزيل، جاري التحقق من الملف...")
            pdlg.open()
            bar.start("جاري الاتصال بالخادم...")
            try:
                path = await run.io_bound(upd.download_patch, res, bar.report)
            finally:
                bar.stop()
                pdlg.close()
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


def update_card() -> None:
    """Settings → «تحديث البرنامج»: this version and the server's, download with a progress bar
    here on the page, then install now or at the next start."""
    import services.updater as upd
    from app_version import APP_VERSION
    from nicegui_ui.transfer_progress import TransferProgress

    state = {"res": None, "path": None}
    with UI.card():
        UI.card_header("تحديث البرنامج", "system_update_alt", icon_css="stat-text-blue")
        cur_lbl = ui.label(f"إصداري الحالي: {APP_VERSION}").classes("text-sm font-bold")
        srv_lbl = ui.label("الإصدار المتاح على الخادم: — (اضغط «التحقق من التحديثات»)").classes("text-sm")
        notes = ui.label("").classes("app-caption whitespace-pre-wrap")
        bar_box = ui.column().classes("w-full gap-1")
        actions = ui.row().classes("w-full gap-2 flex-wrap items-center")

        def show_actions():
            actions.clear()
            res, path = state["res"], state["path"]
            with actions:
                UI.ghost_button("التحقق من التحديثات", icon="refresh", on_click=check)
                if res and res.get("has_update") and not path:
                    UI.primary_button(f"تنزيل {res['latest_version']}", icon="download", on_click=download)
                if path:
                    UI.primary_button("تثبيت الآن (يُغلق البرنامج ويفتحه)", icon="system_update", on_click=install_now)
                    UI.ghost_button("تثبيت عند فتح البرنامج القادم", icon="schedule", on_click=install_later)

        async def check():
            from sync_engine import is_online
            if not is_online():
                srv_lbl.set_text("الإصدار المتاح على الخادم: غير معروف — البرنامج غير متصل")
                return
            srv_lbl.set_text("جاري التحقق...")
            res = await run.io_bound(upd.check_for_updates)
            state["res"], state["path"] = res, None
            if not res:
                srv_lbl.set_text("الإصدار المتاح على الخادم: تعذّر الوصول إلى معلومات التحديث")
            elif res.get("has_update"):
                size = res.get("size_bytes") or 0
                srv_lbl.set_text(f"الإصدار المتاح على الخادم: {res['latest_version']} — يوجد تحديث"
                                 + (f" ({size / 1048576:.1f} MB)" if size else ""))
                notes.set_text(res.get("changelog_ar") or "")
                staged = await run.io_bound(upd.staged_update)
                if staged and staged.get("version") == res["latest_version"]:
                    srv_lbl.set_text(f"التحديث {res['latest_version']} منزَّل وسيُثبَّت عند فتح البرنامج القادم")
                    state["path"] = staged.get("zip")
            else:
                srv_lbl.set_text(f"الإصدار المتاح على الخادم: {res.get('latest_version')} — برنامجك محدَّث")
                notes.set_text("")
            show_actions()

        async def download():
            res = state["res"]
            bar_box.clear()
            with bar_box:
                bar = TransferProgress(f"تنزيل التحديث {res['latest_version']}",
                                       done_text="اكتمل التنزيل، جاري التحقق من الملف...")
            actions.clear()
            bar.start("جاري الاتصال بالخادم...")
            try:
                path = await run.io_bound(upd.download_patch, res, bar.report)
            finally:
                bar.stop()
            if not path:
                bar_box.clear()
                ui.notify("فشل تنزيل ملف التحديث (أو لم يطابق ملف الخادم)", type="negative")
            else:
                ui.notify("اكتمل تنزيل التحديث. اختر وقت التثبيت.", type="positive")
            state["path"] = path
            show_actions()

        async def install_now():
            ui.notify("جاري تثبيت التحديث، سيُغلق البرنامج ويُفتح من جديد...", type="positive")
            await asyncio.sleep(1.0)
            if upd.apply_patch_and_restart(state["path"]):
                os._exit(0)
            ui.notify("تعذر بدء التثبيت", type="negative")

        async def install_later():
            if await run.io_bound(upd.stage_update, state["res"], state["path"]):
                srv_lbl.set_text(f"التحديث {state['res']['latest_version']} سيُثبَّت عند فتح البرنامج القادم")
                ui.notify("سيُثبَّت التحديث عند فتح البرنامج القادم", type="positive")
                actions.clear()
                with actions:
                    UI.ghost_button("التحقق من التحديثات", icon="refresh", on_click=check)

        show_actions()
    ui.timer(0.1, check, once=True)
