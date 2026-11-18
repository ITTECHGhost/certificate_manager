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
        UI.muted_label("يُنزَّل التحديث وأنت تعمل، ثم تختار: تثبيته الآن أو عند فتح البرنامج القادم.")

        def _background():
            dlg.close()
            start_background_download(res)
            ui.notify("بدأ تنزيل التحديث في الخلفية. تابع عملك؛ التقدّم أسفل القائمة الجانبية.", type="info")

        with ui.row().classes("app-dialog-actions"):
            UI.ghost_button("لاحقاً", on_click=dlg.close)
            UI.primary_button("تنزيل في الخلفية", icon="download", on_click=_background)
    dlg.open()



# ── Background download (one per program run; survives page changes) ────────
JOB = {"state": "idle", "done": 0, "total": 0, "started": 0.0, "res": None, "path": None}


def start_background_download(res: dict) -> None:
    """Downloads the patch without blocking the user; JOB holds the progress for any page."""
    import time
    import services.updater as upd
    from nicegui import background_tasks
    if JOB["state"] == "downloading":
        return
    JOB.update(state="downloading", done=0, total=int(res.get("size_bytes") or 0),
               started=time.monotonic(), res=res, path=None)

    def report(done, total):
        JOB["done"], JOB["total"] = done, total

    async def _run():
        path = await run.io_bound(upd.download_patch, res, report)
        JOB.update(state="ready" if path else "failed", path=path)

    background_tasks.create(_run(), name="client-update-download")


def progress_text() -> str:
    """One line for the sidebar / card, '' when nothing is happening."""
    from nicegui_ui.transfer_progress import format_bytes_line
    import time
    st = JOB["state"]
    ver = (JOB["res"] or {}).get("latest_version", "")
    if st == "downloading":
        if JOB["total"]:
            return f"تنزيل التحديث {ver}: " + format_bytes_line(JOB["done"], JOB["total"], time.monotonic() - JOB["started"])
        return f"تنزيل التحديث {ver}..."
    if st == "ready":
        return f"التحديث {ver} جاهز للتثبيت"
    if st == "failed":
        return f"فشل تنزيل التحديث {ver}"
    return ""


async def install_now(path: str) -> None:
    import services.updater as upd
    ui.notify("جاري تثبيت التحديث، سيُغلق البرنامج ويُفتح من جديد...", type="positive")
    await asyncio.sleep(1.0)
    if upd.apply_patch_and_restart(path):
        os._exit(0)
    ui.notify("تعذر بدء التثبيت", type="negative")


async def install_at_next_start(res: dict, path: str) -> bool:
    import services.updater as upd
    ok = await run.io_bound(upd.stage_update, res, path)
    if ok:
        JOB["state"] = "staged"
        ui.notify("سيُثبَّت التحديث عند فتح البرنامج القادم", type="positive")
    return ok


def update_card() -> None:
    """Settings → «تحديث البرنامج»: this version and the server's; the download runs in the
    background (the user may leave this page), then install now or at the next start."""
    import services.updater as upd
    from app_version import APP_VERSION

    with UI.card():
        UI.card_header("تحديث البرنامج", "system_update_alt", icon_css="stat-text-blue")
        ui.label(f"إصداري الحالي: {APP_VERSION}").classes("text-sm font-bold")
        srv_lbl = ui.label("الإصدار المتاح على الخادم: —").classes("text-sm")
        notes = ui.label("").classes("app-caption whitespace-pre-wrap")
        bar = ui.linear_progress(value=0, show_value=False, size="12px").classes("w-full")
        bar_txt = ui.label("").classes("app-caption")
        UI.muted_label("التنزيل يجري في الخلفية: تستطيع متابعة عملك وترك هذه الصفحة؛ التقدّم يظهر أسفل القائمة الجانبية.")
        actions = ui.row().classes("w-full gap-2 flex-wrap items-center")
        shown = {"state": None}

        def draw():
            st = JOB["state"]
            bar.set_visibility(st == "downloading")
            if st == "downloading" and JOB["total"]:
                bar.set_value(min(JOB["done"] / JOB["total"], 1.0))
            bar_txt.set_text(progress_text())
            if shown["state"] == st:
                return
            shown["state"] = st
            actions.clear()
            res = JOB["res"]
            with actions:
                UI.ghost_button("التحقق من التحديثات", icon="refresh", on_click=check)
                if st in ("idle", "failed") and res and res.get("has_update"):
                    UI.primary_button(f"تنزيل {res['latest_version']}", icon="download",
                                      on_click=lambda: (start_background_download(res), draw()))
                if st == "ready":
                    UI.primary_button("تثبيت الآن (يُغلق البرنامج ويفتحه)", icon="system_update",
                                      on_click=lambda: install_now(JOB["path"]))
                    UI.ghost_button("تثبيت عند فتح البرنامج القادم", icon="schedule",
                                    on_click=lambda: install_at_next_start(JOB["res"], JOB["path"]))

        async def check():
            from sync_engine import is_online
            if not is_online():
                srv_lbl.set_text("الإصدار المتاح على الخادم: غير معروف — البرنامج غير متصل")
                return
            srv_lbl.set_text("جاري التحقق...")
            res = await run.io_bound(upd.check_for_updates)
            if not res:
                srv_lbl.set_text("الإصدار المتاح على الخادم: تعذّر الوصول إلى معلومات التحديث")
                return
            if res.get("has_update"):
                size = res.get("size_bytes") or 0
                srv_lbl.set_text(f"الإصدار المتاح على الخادم: {res['latest_version']} — يوجد تحديث"
                                 + (f" ({size / 1048576:.1f} MB)" if size else ""))
                notes.set_text(res.get("changelog_ar") or "")
                staged = await run.io_bound(upd.staged_update)
                if staged and staged.get("version") == res["latest_version"]:
                    JOB.update(state="staged", res=res, path=staged.get("zip"))
                    srv_lbl.set_text(f"التحديث {res['latest_version']} منزَّل وسيُثبَّت عند فتح البرنامج القادم")
                elif JOB["state"] not in ("downloading", "ready"):
                    JOB.update(state="idle", res=res)
            else:
                srv_lbl.set_text(f"الإصدار المتاح على الخادم: {res.get('latest_version')} — برنامجك محدَّث")
                notes.set_text("")
            shown["state"] = None
            draw()

        draw()
    ui.timer(0.5, draw)
    ui.timer(0.1, check, once=True)
