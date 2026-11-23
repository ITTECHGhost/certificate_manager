"""Scanning order papers with the office scanner (Windows WIA, through pywin32; no new library).

scan_pages() asks the chosen scanner for pages from the feeder (ADF: every sheet until the tray
is empty) or the glass (one page), at the chosen resolution, and saves them as JPEG files in a
new folder under <data>/scans/. The pages are then given to the AI (Gemini) to make the CSV;
a local OCR model comes later.
"""
import os
from datetime import datetime
from pathlib import Path

import app_paths

SOURCES = {"feeder": "المغذّي (عدة أوراق)", "flatbed": "الزجاج (ورقة واحدة)"}
DPI_OPTIONS = {200: "200", 300: "300 (مستحسن)", 400: "400"}
FILE_TYPES = {"pdf": "ملف PDF واحد", "jpg": "صور JPEG"}
PAGE_SIZES = {"A4": "A4", "auto": "حجم الماسح"}
_A4_INCHES = (8.27, 11.69)

# WIA constants
_SCANNER_TYPE = 1
_DOCUMENT_HANDLING_SELECT = 3088   # device property
_DOCUMENT_HANDLING_STATUS = 3087
_PAGES = 3096
_FEEDER, _FLATBED = 1, 2
_FEED_READY = 1
_H_DPI, _V_DPI, _COLOR_INTENT = 6147, 6148, 6146
_X_EXTENT, _Y_EXTENT = 6151, 6152
_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
_PAPER_EMPTY = (-2145320957, 0x80210003)   # WIA_ERROR_PAPER_EMPTY (signed / unsigned)
_INVALID_ARG = (-2147024809, 0x80070057)   # E_INVALIDARG: the driver refused a setting
# What to set, from all settings to the scanner's own defaults (each level is tried once when
# the driver answers "the parameter is incorrect" before the first page).
SETTING_LEVELS = ("all", "no_page_size", "source_only", "feeder_bare")


def scans_root() -> Path:
    return app_paths.data_path("scans")


def new_batch_folder(now=None) -> Path:
    """A new folder for one scanning run, named by date and time (never overwrites)."""
    now = now or datetime.now()
    base = scans_root() / now.strftime("%Y-%m-%d %H-%M-%S")
    folder, n = base, 2
    while folder.exists():
        folder = base.with_name(f"{base.name} ({n})")
        n += 1
    folder.mkdir(parents=True)
    return folder


def _codes(exc) -> set:
    codes = {getattr(exc, "hresult", None)}
    for arg in getattr(exc, "args", ()) or ():
        if isinstance(arg, int):
            codes.add(arg)
        elif isinstance(arg, tuple):
            codes.update(a for a in arg if isinstance(a, int))
    return codes


def is_invalid_setting(exc) -> bool:
    """The driver refused a setting (E_INVALIDARG): try again with fewer settings."""
    return bool(_codes(exc) & set(_INVALID_ARG))


def is_paper_empty(exc) -> bool:
    """The feeder ran out of sheets (normal end of a feeder run)."""
    codes = {getattr(exc, "hresult", None)}
    for arg in getattr(exc, "args", ()) or ():
        if isinstance(arg, int):
            codes.add(arg)
        elif isinstance(arg, tuple):
            codes.update(a for a in arg if isinstance(a, int))
    return bool(codes & set(_PAPER_EMPTY))


def _set_prop(props, prop_id, value):
    for p in props:
        if p.PropertyID == prop_id:
            try:
                if isinstance(value, int) and getattr(p, "SubType", 0) == 1:   # a range: stay inside it
                    value = max(int(p.SubTypeMin), min(int(p.SubTypeMax), value))
                p.Value = value
            except Exception:
                pass   # not every scanner supports every setting
            return


def _com():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    return win32com.client


def list_scanners() -> dict:
    """{device id: name} of the scanners Windows knows (WIA)."""
    client = _com()
    manager = client.Dispatch("WIA.DeviceManager")
    out = {}
    for i in range(1, manager.DeviceInfos.Count + 1):
        info = manager.DeviceInfos.Item(i)
        if info.Type == _SCANNER_TYPE:
            out[info.DeviceID] = info.Properties("Name").Value
    return out


def _transfer_pages(item, source, folder: Path, max_pages: int, progress=None) -> list:
    """Takes pages from the scanner item until the feeder is empty (or one page from the glass)."""
    saved = []
    while len(saved) < (max_pages if source == "feeder" else 1):
        try:
            image = item.Transfer(_JPEG)
        except Exception as exc:
            if source == "feeder" and saved and is_paper_empty(exc):
                break
            if source == "feeder" and not saved and is_paper_empty(exc):
                raise RuntimeError("المغذّي فارغ: ضع أوراق الأمر في المغذّي ثم أعد المحاولة") from exc
            raise
        path = folder / f"page_{len(saved) + 1:03d}.jpg"
        image.SaveFile(str(path))
        saved.append(path)
        if progress:
            progress(len(saved))
    return saved


def scan_pages(device_id: str, source: str = "feeder", dpi: int = 300, color: bool = True,
               max_pages: int = 200, progress=None, file_type: str = "pdf",
               page_size: str = "A4") -> tuple[Path, list]:
    """Scans into a new folder; returns (folder, [files]): one PDF (file_type pdf) or the JPEG
    pages. Raises RuntimeError in Arabic."""
    if source not in SOURCES:
        raise ValueError("مصدر غير معروف")
    folder = new_batch_folder()
    pages = []
    try:
        for level in SETTING_LEVELS:
            item = _prepare(device_id, source, dpi, color, page_size, level)
            try:
                pages = _transfer_pages(item, source, folder, max_pages, progress)
                break
            except Exception as exc:
                if is_invalid_setting(exc) and not any(folder.iterdir()) and level != SETTING_LEVELS[-1]:
                    continue   # the driver refused a setting: try again with fewer
                raise
    except Exception as exc:
        if not any(folder.iterdir()):
            folder.rmdir()
        if is_invalid_setting(exc):
            raise RuntimeError("رفض الماسح إعدادات المسح حتى الافتراضية منها. تأكد أن الأوراق في المغذّي، "
                               "أو جرّب «الزجاج»، أو امسح من برنامج ويندوز ثم ارفع الملف.") from exc
        raise
    if file_type == "pdf":
        return folder, [pages_to_pdf(pages, folder / f"{folder.name}.pdf")]
    return folder, pages


def _prepare(device_id, source, dpi, color, page_size, level):
    """Connects to the scanner and sets what this level allows; returns the scan item."""
    client = _com()
    manager = client.Dispatch("WIA.DeviceManager")
    device = None
    for i in range(1, manager.DeviceInfos.Count + 1):
        info = manager.DeviceInfos.Item(i)
        if info.DeviceID == device_id:
            device = info.Connect()
            break
    if device is None:
        raise RuntimeError("الماسح غير متصل أو مطفأ")
    _set_prop(device.Properties, _DOCUMENT_HANDLING_SELECT, _FEEDER if source == "feeder" else _FLATBED)
    if source == "feeder" and level != "feeder_bare":
        # one sheet per Transfer (the loop asks again until the tray is empty). 0 = "all sheets"
        # is refused by some drivers (Canon MF270: E_INVALIDARG even with default settings).
        _set_prop(device.Properties, _PAGES, 1)
    item = device.Items(1)
    if level in ("source_only", "feeder_bare"):
        return item
    _set_prop(item.Properties, _H_DPI, int(dpi))
    _set_prop(item.Properties, _V_DPI, int(dpi))
    _set_prop(item.Properties, _COLOR_INTENT, 1 if color else 2)   # 1 color, 2 grayscale
    if level == "all" and page_size == "A4":
        _set_prop(item.Properties, _X_EXTENT, int(_A4_INCHES[0] * int(dpi)))
        _set_prop(item.Properties, _Y_EXTENT, int(_A4_INCHES[1] * int(dpi)))
    return item


def pages_to_pdf(pages: list, pdf_path: Path) -> Path:
    """All scanned pages in one PDF (the page images are kept beside it)."""
    from PIL import Image
    images = [Image.open(p).convert("RGB") for p in pages]
    if not images:
        raise RuntimeError("لا توجد صفحات")
    images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:], resolution=300.0)
    return pdf_path


def open_folder(path=None) -> None:
    folder = Path(path) if path else scans_root()
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(str(folder))   # Windows Explorer
