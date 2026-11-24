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


_RPC_FAILED = -2147023170


class _NoImage(Exception):
    """The driver gave None for the first page (Canon MF270 feeder with some settings)."""


def _transfer_pages(item, source, folder: Path, max_pages: int, progress=None) -> list:
    """Takes pages from the scanner item until the feeder is empty (or one page from the glass)."""
    saved = []
    while len(saved) < (max_pages if source == "feeder" else 1):
        try:
            image = item.Transfer(_JPEG)
        except Exception as exc:
            if source == "feeder" and saved and (is_paper_empty(exc) or _RPC_FAILED in _codes(exc)):
                break
            if source == "feeder" and not saved and is_paper_empty(exc):
                raise RuntimeError("المغذّي فارغ: ضع أوراق الأمر في المغذّي ثم أعد المحاولة") from exc
            raise
        path = folder / f"page_{len(saved) + 1:03d}.jpg"
        if image is None:
            if saved:
                break
            raise _NoImage()
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
    if source == "feeder":
        try:
            pages = _scan_feeder_winrt(_scanner_name(device_id), folder, dpi, color, max_pages)
        except Exception:
            if not any(folder.iterdir()):
                folder.rmdir()
            raise
        if progress:
            progress(len(pages))
        if file_type == "pdf":
            return folder, [pages_to_pdf(pages, folder / f"{folder.name}.pdf")]
        return folder, pages
    try:
        for level in SETTING_LEVELS:
            item = _prepare(device_id, source, dpi, color, page_size, level)
            try:
                pages = _transfer_pages(item, source, folder, max_pages, progress)
                break
            except Exception as exc:
                if ((is_invalid_setting(exc) or isinstance(exc, _NoImage))
                        and not any(folder.iterdir()) and level != SETTING_LEVELS[-1]):
                    continue   # the driver refused a setting / gave no image: try again with fewer
                raise
    except Exception as exc:
        if not any(folder.iterdir()):
            folder.rmdir()
        if isinstance(exc, _NoImage):
            raise RuntimeError("لم يُرجع الماسح أي صورة: جرّب المسح من الزجاج") from exc
        if is_invalid_setting(exc):
            raise RuntimeError("رفض الماسح إعدادات المسح حتى الافتراضية منها. تأكد أن الأوراق في المغذّي، "
                               "أو جرّب «الزجاج»، أو امسح من برنامج ويندوز ثم ارفع الملف.") from exc
        raise
    if file_type == "pdf":
        return folder, [pages_to_pdf(pages, folder / f"{folder.name}.pdf")]
    return folder, pages


def _scanner_name(device_id) -> str:
    try:
        return list_scanners().get(device_id, "")
    except Exception:
        return ""


# Feeder through Windows.Devices.Scanners (the API of the Windows Scan app), run by Windows
# PowerShell: no new library. WIA's item.Transfer on the Canon MF270 (eSCL driver) pulls every
# sheet through and returns None (seen 2026-11-24, DEV laptop); this API returns one file per sheet.
_WINRT_PS = r"""
param([string]$Out, [string]$Name, [int]$Dpi, [int]$Color)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Devices.Scanners.ImageScanner, Windows.Devices.Scanners, ContentType = WindowsRuntime]
$null = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFolder, Windows.Storage, ContentType = WindowsRuntime]
$ext = [System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 }
$m1 = $ext | ? { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }
$m2 = $ext | ? { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperationWithProgress`2' }
function Wait-Op($t) {
  while (-not $t.IsCompleted) { Start-Sleep -Milliseconds 100 }
  if ($t.IsFaulted) { $e = $t.Exception.InnerException; "ERR $($e.HResult) $($e.Message -replace '\s+', ' ')"; exit 1 }
  $t.Result
}
function Await($op, [Type]$t) { Wait-Op ($m1.MakeGenericMethod($t).Invoke($null, @($op))) }
$devs = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync([Windows.Devices.Scanners.ImageScanner]::GetDeviceSelector())) ([Windows.Devices.Enumeration.DeviceInformationCollection])
if ($devs.Count -eq 0) { 'ERR 0 no scanner'; exit 1 }
$dev = $devs | ? { $_.Name -eq $Name } | Select-Object -First 1
if (-not $dev) { $dev = $devs[0] }
$sc = Await ([Windows.Devices.Scanners.ImageScanner]::FromIdAsync($dev.Id)) ([Windows.Devices.Scanners.ImageScanner])
$f = $sc.FeederConfiguration
$f.Format = 'Jpeg'
if ($f.DesiredResolution.DpiX -ne $Dpi) { try { $f.DesiredResolution = New-Object Windows.Devices.Scanners.ImageScannerResolution -Property @{DpiX = $Dpi; DpiY = $Dpi} } catch {} }
$mode = if ($Color) { 'Color' } else { 'Grayscale' }
if ("$($f.ColorMode)" -ne $mode) { try { $f.ColorMode = $mode } catch {} }
$folder = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($Out)) ([Windows.Storage.StorageFolder])
$r = Wait-Op ($m2.MakeGenericMethod([Windows.Devices.Scanners.ImageScannerScanResult], [uint32]).Invoke($null, @($sc.ScanFilesToFolderAsync('Feeder', $folder))))
foreach ($file in $r.ScannedFiles) { "FILE $($file.Path)" }
"""

_WINRT_EMPTY = -2145844748   # "Internal server error (500)": the MF270 answers this when the feeder is empty
_WINRT_BUSY = -2145320954    # WIA_ERROR_BUSY


def _run_powershell(script: str, args: list) -> tuple[int, str]:
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8-sig") as fh:
        fh.write(script)
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", fh.name, *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=1800, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return proc.returncode, proc.stdout + proc.stderr
    finally:
        Path(fh.name).unlink(missing_ok=True)


def _scan_feeder_winrt(name: str, folder: Path, dpi: int, color: bool, max_pages: int) -> list:
    """All sheets in the feeder → page_001.jpg … in folder. Raises RuntimeError in Arabic."""
    code, out = _run_powershell(_WINRT_PS, ["-Out", str(folder), "-Name", name or "",
                                            "-Dpi", str(int(dpi)), "-Color", "1" if color else "0"])
    files = [Path(line[5:].strip()) for line in out.splitlines() if line.startswith("FILE ")]
    if not files:
        err = next((line for line in out.splitlines() if line.startswith("ERR ")), out.strip()[-300:])
        if str(_WINRT_EMPTY) in err:
            raise RuntimeError("المغذّي فارغ: ضع أوراق الأمر في المغذّي ثم أعد المحاولة")
        if str(_WINRT_BUSY) in err:
            raise RuntimeError("الماسح مشغول: أعد شاشة الطابعة إلى الرئيسية وانتظر قليلًا ثم أعد المحاولة")
        raise RuntimeError(f"تعذّر المسح من المغذّي: {err}")
    pages = []
    for i, src in enumerate(files[:max_pages], 1):
        dst = folder / f"page_{i:03d}.jpg"
        Path(src).replace(dst)
        pages.append(dst)
    return pages


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
    """All scanned pages in one PDF; the page images were only a step and are deleted."""
    from PIL import Image
    images = []
    for p in pages:
        with Image.open(p) as im:
            images.append(im.convert("RGB"))
    if not images:
        raise RuntimeError("لا توجد صفحات")
    images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:], resolution=300.0)
    for p in pages:
        Path(p).unlink(missing_ok=True)
    return pdf_path


def open_folder(path=None) -> None:
    folder = Path(path) if path else scans_root()
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(str(folder))   # Windows Explorer
