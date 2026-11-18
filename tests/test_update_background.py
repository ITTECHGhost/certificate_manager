import asyncio

import nicegui_ui.update_prompt as up


def _run(res, fake):
    import services.updater as upd
    from nicegui import background_tasks
    orig, orig_create, orig_io = upd.download_patch, background_tasks.create, up.run.io_bound
    tasks = []
    upd.download_patch = fake
    background_tasks.create = lambda coro, name=None: tasks.append(coro)
    up.run.io_bound = lambda f, *a: asyncio.sleep(0, result=f(*a))
    try:
        up.JOB["state"] = "idle"
        up.start_background_download(res)
        assert up.JOB["state"] == "downloading"
        up.start_background_download(res)          # a second click starts nothing
        assert len(tasks) == 1
        asyncio.run(tasks[0])
    finally:
        upd.download_patch, background_tasks.create, up.run.io_bound = orig, orig_create, orig_io


def test_download_reports_progress_and_ready():
    def fake(res, report):
        report(50, 100)
        assert "50" in up.progress_text() or "%" in up.progress_text()
        return "C:/x/patch_v9.9.9.zip"
    _run({"latest_version": "9.9.9", "size_bytes": 100}, fake)
    assert up.JOB["state"] == "ready" and up.progress_text() == "التحديث 9.9.9 جاهز للتثبيت"


def test_failed_download_says_so():
    _run({"latest_version": "9.9.9"}, lambda res, report: None)
    assert up.JOB["state"] == "failed" and "فشل" in up.progress_text()
