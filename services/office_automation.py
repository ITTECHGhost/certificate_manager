# =============================================================================
# services/office_automation.py — Word (COM) conversion and Windows printing
# =============================================================================
# Moved from nicegui_screens/certificate_screen.py, which re-imports every name.

import os
import logging

log = logging.getLogger(__name__)


def generate_pdf_from_docx(docx_path: str) -> str | None:
    """Converts a rendered Word .docx document into a .pdf file for direct print preview."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_docx = os.path.abspath(docx_path)
    abs_pdf = os.path.splitext(abs_docx)[0] + ".pdf"
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_docx)
        doc.SaveAs(abs_pdf, FileFormat=17)  # 17 = wdFormatPDF
        doc.Close()
        return abs_pdf
    except Exception as err:
        log.error(f"Error converting docx to pdf: {err}")
        return None
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def convert_docx_to_html(docx_path: str) -> str | None:
    """Converts a rendered Word .docx document into a filtered .html file for in-app web preview."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_docx = os.path.abspath(docx_path)
    abs_html = os.path.splitext(abs_docx)[0] + ".html"
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_docx)
        doc.SaveAs(abs_html, FileFormat=10)  # 10 = wdFormatFilteredHTML
        doc.Close()
        return abs_html
    except Exception as err:
        log.error(f"Error converting docx to html: {err}")
        return None
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


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
    """Sends a .docx or .pdf file directly to the selected Windows printer via Word COM."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_path = os.path.abspath(file_path)
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        if printer_name:
            try:
                word.ActivePrinter = printer_name
            except Exception as pe:
                log.warning(f"Could not set ActivePrinter to '{printer_name}': {pe}")
        doc = word.Documents.Open(abs_path)
        doc.PrintOut(Copies=copies)
        doc.Close(False)
        return True
    except Exception as e:
        log.error(f"Error printing to {printer_name}: {e}")
        return False
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
