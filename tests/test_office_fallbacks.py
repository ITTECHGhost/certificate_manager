"""Without Word or a print spooler the Office helpers return a value; they never raise."""
import win32com.client
import win32print

import nicegui_screens.certificate_screen as certificate_screen


def _no_word(name):
    raise Exception("Invalid class string")


def _no_spooler(*args, **kwargs):
    raise Exception("The print spooler is not running")


def test_pdf_and_print_without_word(tmp_path, monkeypatch):
    monkeypatch.setattr(win32com.client, "Dispatch", _no_word)
    docx = tmp_path / "x.docx"
    docx.write_bytes(b"not a real document")
    assert certificate_screen.generate_pdf_from_docx(str(docx)) is None
    assert certificate_screen.convert_docx_to_html(str(docx)) is None
    assert certificate_screen.print_file_to_printer(str(docx), "Any Printer") is False


def test_printers_without_spooler(monkeypatch):
    monkeypatch.setattr(win32print, "EnumPrinters", _no_spooler)
    monkeypatch.setattr(win32print, "GetDefaultPrinter", _no_spooler)
    assert certificate_screen.get_installed_printers() == ["Default Printer"]
    assert certificate_screen.get_default_printer() == "Default Printer"
