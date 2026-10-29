# =============================================================================
# services/office_automation.py — Word (COM) conversion and Windows printing
# =============================================================================
# Moved from nicegui_screens/certificate_screen.py, which re-imports every name.

import os
import atexit
import logging
import queue
import threading
from concurrent.futures import Future

log = logging.getLogger(__name__)


# One hidden Word stays open for the whole session, owned by a single worker
# thread (COM objects only work on the thread that created them). Starting Word
# is the slow part, so it happens once instead of on every preview.
# DispatchEx starts our own Word process, so the user's open Word windows are
# never reused or closed by us.
# A plain daemon thread (not a ThreadPoolExecutor): the pool refuses new work
# once Python starts exiting, which would leave the hidden Word running.
_word = None
_jobs: "queue.Queue[tuple[object, Future]]" = queue.Queue()


def _word_loop():
    while True:
        fn, fut = _jobs.get()
        try:
            fut.set_result(fn())
        except Exception as err:
            fut.set_exception(err)


threading.Thread(target=_word_loop, name="word", daemon=True).start()


def _submit(fn) -> Future:
    fut = Future()
    _jobs.put((fn, fut))
    return fut


def _get_word():
    global _word
    import pythoncom
    import win32com.client
    if _word is not None:
        try:
            _word.Documents.Count  # still alive?
            return _word
        except Exception:
            _word = None
    pythoncom.CoInitialize()
    _word = win32com.client.DispatchEx("Word.Application")
    _word.Visible = False
    _word.DisplayAlerts = 0
    return _word


def _run_in_word(job):
    """Runs job(word) on the Word thread; retries once with a fresh Word if it died."""
    def task():
        global _word
        try:
            return job(_get_word())
        except Exception:
            _word = None
            return job(_get_word())
    return _submit(task).result()


def warm_up_word() -> None:
    """Starts the hidden Word in the background so the first preview is fast."""
    def task():
        try:
            _get_word()
        except Exception as err:
            log.warning(f"Word is not available: {err}")
    _submit(task)


def _quit_word():
    def task():
        global _word
        if _word is not None:
            try:
                _word.Quit(False)
            except Exception:
                pass
            _word = None
    try:
        _submit(task).result(timeout=10)
    except Exception:
        pass


atexit.register(_quit_word)


def generate_pdf_from_docx(docx_path: str) -> str | None:
    """Converts a rendered Word .docx document into a .pdf file for preview and printing."""
    abs_docx = os.path.abspath(docx_path)
    abs_pdf = os.path.splitext(abs_docx)[0] + ".pdf"

    def job(word):
        doc = word.Documents.Open(abs_docx, ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.SaveAs(abs_pdf, FileFormat=17)  # 17 = wdFormatPDF
        finally:
            doc.Close(False)
        return abs_pdf

    try:
        return _run_in_word(job)
    except Exception as err:
        log.error(f"Error converting docx to pdf: {err}")
        return None


def get_installed_printers() -> list[str]:
    """Queries installed Windows local and network printer names."""
    try:
        import win32print
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        printer_names = [p[2] for p in printers]
        if not printer_names:
            default_p = win32print.GetDefaultPrinter()
            if default_p:
                printer_names = [default_p]
        return printer_names
    except Exception:
        return ["Default Printer"]


def get_default_printer() -> str:
    """Returns the default printer name on Windows."""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        printers = get_installed_printers()
        return printers[0] if printers else "Default Printer"


def print_file_to_printer(file_path: str, printer_name: str, copies: int = 1) -> bool:
    """Sends a .docx file directly to the selected Windows printer through the hidden Word."""
    abs_path = os.path.abspath(file_path)

    def job(word):
        if printer_name:
            try:
                word.ActivePrinter = printer_name
            except Exception as pe:
                log.warning(f"Could not set ActivePrinter to '{printer_name}': {pe}")
        doc = word.Documents.Open(abs_path, ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.PrintOut(Copies=copies, Background=False)
        finally:
            doc.Close(False)
        return True

    try:
        return _run_in_word(job)
    except Exception as e:
        log.error(f"Error printing to {printer_name}: {e}")
        return False
