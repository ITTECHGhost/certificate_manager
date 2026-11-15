# =============================================================================
# nicegui_ui/transfer_progress.py — one progress bar for uploads and downloads
#
# Usage (inside a NiceGUI container):
#     bar = TransferProgress("إرسال التحديث إلى الخادم")
#     bar.start()
#     try:
#         result = await run.io_bound(work, ..., bar.report)   # report(done, total) from any thread
#     finally:
#         bar.stop()
#
# report() only stores numbers (it runs on a worker thread); a UI timer draws them.
# unit="bytes" shows MB, speed and time left; unit="pages" shows "الصفحة 3 من 12".
# =============================================================================

import time
from typing import Optional

from nicegui import ui


def format_bytes_line(done: int, total: int, elapsed: float) -> str:
    """'120.4 / 288.8 MB (42%) — 3.1 MB/ث، متبقٍ 0:54' (pure: unit-tested)."""
    frac = done / total if total else 0.0
    text = f"{done / 1048576:.1f} / {total / 1048576:.1f} MB ({frac * 100:.0f}%)"
    if total and done >= total:
        return text + " — اكتمل النقل"
    speed = done / elapsed if elapsed > 0 else 0
    if speed > 0 and elapsed > 2:
        left = int((total - done) / speed)
        text += f" — {speed / 1048576:.1f} MB/ث، متبقٍ {left // 60}:{left % 60:02d}"
    return text


def format_pages_line(done: int, total: int) -> str:
    return f"الصفحة {done} من {total}" if total else f"الصفحة {done}"


class TransferProgress:
    """A titled bar + one text line, hidden until start()."""

    def __init__(self, title: str, unit: str = "bytes", done_text: str = ""):
        self.unit, self.done_text = unit, done_text
        self._done, self._total, self._start = 0, 0, 0.0
        self._timer: Optional[ui.timer] = None
        with ui.column().classes("w-full gap-1") as self.box:
            self.title = ui.label(title).classes("app-caption font-semibold")
            self.bar = ui.linear_progress(value=0, show_value=False, size="12px").classes("w-full")
            self.text = ui.label("").classes("app-caption").style("direction:rtl")
        self.box.set_visibility(False)

    def report(self, done: int, total: int) -> None:
        """Called from the worker thread: store only."""
        self._done, self._total = done, total

    def start(self, first_text: str = "جاري الاتصال...") -> None:
        self._done, self._total, self._start = 0, 0, time.monotonic()
        self.bar.set_value(0)
        self.text.set_text(first_text)
        self.box.set_visibility(True)
        self._timer = ui.timer(0.3, self._draw)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.box.set_visibility(False)

    def _draw(self) -> None:
        done, total = self._done, self._total
        if not total:
            return
        self.bar.set_value(min(done / total, 1.0))
        if self.unit == "pages":
            self.text.set_text(format_pages_line(done, total))
        else:
            line = format_bytes_line(done, total, time.monotonic() - self._start)
            if done >= total and self.done_text:
                line = line.replace("اكتمل النقل", self.done_text)
            self.text.set_text(line)
