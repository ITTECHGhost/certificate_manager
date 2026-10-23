# =============================================================================
# utils/file_delivery.py — Bulletproof Native Desktop & Web File Delivery Helper
# =============================================================================

import os
import re
import time
import logging
import subprocess
from pathlib import Path
from typing import Union, Optional

from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

log = logging.getLogger(__name__)


def get_downloads_dir() -> Path:
    """
    Returns the user's primary Downloads folder on Windows,
    falling back to Desktop or an application exports directory if inaccessible.
    """
    try:
        downloads = Path.home() / "Downloads"
        if downloads.exists() and os.access(str(downloads), os.W_OK):
            return downloads
    except Exception as exc:
        log.warning(f"Error accessing Downloads directory: {exc}")

    try:
        desktop = Path.home() / "Desktop"
        if desktop.exists() and os.access(str(desktop), os.W_OK):
            return desktop
    except Exception as exc:
        log.warning(f"Error accessing Desktop directory: {exc}")

    fallback = Path.cwd() / "exports"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def sanitize_filename(filename: str, fallback_ext: str = ".xlsx") -> str:
    """Removes invalid Windows filesystem characters and ensures a clean filename."""
    name = re.sub(r'[<>:"/\\|?*]', '_', filename or "").strip()
    if not name:
        name = f"export_{time.strftime('%Y%m%d_%H%M%S')}{fallback_ext}"
    return name


def format_file_size(size_bytes: int) -> str:
    """Format bytes into readable KB / MB strings."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def save_file_to_downloads(content: Union[bytes, str, Path], filename: str) -> Path:
    """
    Directly writes bytes or source file to the user's Downloads folder.
    If the target file is locked (e.g. already open in Microsoft Excel),
    a timestamped copy is generated automatically to prevent PermissionError.
    """
    target_dir = get_downloads_dir()
    clean_name = sanitize_filename(filename)
    stem, ext = os.path.splitext(clean_name)
    target_path = target_dir / clean_name

    # Read binary bytes
    if isinstance(content, (str, Path)):
        with open(content, "rb") as f:
            file_bytes = f.read()
    elif isinstance(content, bytes):
        file_bytes = content
    else:
        file_bytes = bytes(content)

    # Attempt direct write; if locked by Excel, write timestamped version
    try:
        with open(target_path, "wb") as f:
            f.write(file_bytes)
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{stem}_{ts}{ext}"
        with open(target_path, "wb") as f:
            f.write(file_bytes)

    return target_path


def open_file_externally(path: Union[str, Path]) -> bool:
    """Opens the saved file in Microsoft Excel or associated system application."""
    target_str = str(os.path.abspath(str(path)))
    try:
        os.startfile(target_str)
        return True
    except Exception as exc:
        log.warning(f"Could not open file with default handler: {exc}")
        try:
            subprocess.Popen(["cmd", "/c", "start", "", target_str], shell=True)
            return True
        except Exception as inner_exc:
            log.error(f"Failed fallback open: {inner_exc}")
            return False


def show_in_file_manager(path: Union[str, Path]) -> bool:
    """Opens Windows File Explorer with the specific saved file selected/highlighted."""
    target_str = str(os.path.abspath(str(path)))
    try:
        subprocess.Popen(["explorer", f"/select,{target_str}"])
        return True
    except Exception as exc:
        log.warning(f"Could not open file in explorer: {exc}")
        try:
            # Fallback to opening containing folder
            folder_str = str(os.path.dirname(target_str))
            subprocess.Popen(["explorer", folder_str])
            return True
        except Exception:
            return False


def show_delivery_modal(target_path: Path, title: str, auto_opened: bool = True):
    """
    Renders a clean, high-contrast modal dialog notifying the user of the saved file
    with direct 1-click action buttons to open in Excel or reveal in Windows Explorer.
    """
    try:
        file_size_str = format_file_size(target_path.stat().st_size)
    except Exception:
        file_size_str = "غير معروف"

    with ui.dialog() as dlg, ui.card().classes(
        "app-card p-6 rounded-2xl w-[520px] max-w-[95vw] gap-4 shadow-2xl border border-[var(--border-default)]"
    ):
        # Header Row
        with ui.row().classes("w-full items-center justify-between pb-3 border-b border-[var(--border-default)]"):
            with ui.row().classes("items-center gap-3"):
                with ui.avatar(icon="task_alt", color="emerald-600", text_color="white", size="md").classes("shadow-sm"):
                    pass
                with ui.column().classes("gap-0"):
                    ui.label(title).classes("text-base font-bold app-text-primary")
                    status_sub = "تم حفظ الملف وتجهيزه مباشرة في مجلد التنزيلات"
                    if auto_opened:
                        status_sub += " وجاري فتحه في Excel..."
                    ui.label(status_sub).classes("text-xs text-emerald-500 font-medium")
            ui.button(icon="close", on_click=dlg.close).classes("app-btn-secondary p-1 rounded-lg text-xs").props("flat round dense")

        # File Details Container
        with ui.column().classes("w-full bg-[var(--bg-card-secondary)] p-3.5 rounded-xl border border-[var(--border-default)] gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("table_chart", size="xs").classes("text-emerald-500")
                    ui.label(target_path.name).classes("font-bold text-sm app-text-primary break-all")
                ui.badge(file_size_str, color="emerald-700").classes("text-[11px] font-mono px-2")

            with ui.row().classes("w-full items-center gap-1.5 text-xs app-text-muted mt-1"):
                ui.icon("folder_open", size="xs").classes("shrink-0 text-slate-400")
                ui.label(f"المسار: {target_path}").classes("font-mono text-[11px] break-all leading-tight opacity-90")

        # Action Buttons
        with ui.row().classes("w-full items-center justify-end gap-2.5 pt-2"):
            UI.secondary_button("إغلاق / Close", icon="close", on_click=dlg.close).classes("text-xs px-3 py-1.5")

            def on_show_folder():
                show_in_file_manager(target_path)
                ui.notify("تم فتح مجلد التنزيلات في Windows Explorer", type="info")

            UI.secondary_button("📁 عرض في المجلد", icon="folder", on_click=on_show_folder).classes("text-xs px-3 py-1.5").tooltip("عرض الملف وتحديده في مجلد التنزيلات")

            def on_open_excel():
                ok = open_file_externally(target_path)
                if ok:
                    ui.notify("تم فتح الملف في البرنامج المرتبط (Excel)", type="positive")
                else:
                    ui.notify("تعذر فتح الملف تلقائياً، يرجى فتحه من مجلد التنزيلات", type="warning")

            UI.success_button("📊 فتح الملف الآن", icon="launch", on_click=on_open_excel).classes("text-xs px-4 py-1.5 font-bold shadow-md").tooltip("فتح ملف الإكسل مباشرة للبدء بتعبئته")

    dlg.open()


def deliver_file(
    content: Union[bytes, str, Path],
    filename: str,
    title: str = "تم تجهيز وتنزيل ملف Excel بنجاح",
    auto_open: bool = True,
    show_modal: bool = True,
) -> Path:
    """
    Complete bulletproof file delivery pipeline:
    1. Saves content directly to user's Windows Downloads directory.
    2. Calls ui.download() as fallback for web browser sessions.
    3. Auto-opens the file in Microsoft Excel if auto_open=True.
    4. Shows a high-contrast modal with 1-click actions and notification.
    """
    clean_name = sanitize_filename(filename)
    target_path = save_file_to_downloads(content, clean_name)
    log.info(f"File successfully delivered to: {target_path} ({target_path.stat().st_size} bytes)")

    # 1. Trigger browser download as fallback for web sessions
    try:
        if isinstance(content, (str, Path)):
            ui.download(str(content), filename=clean_name)
        else:
            ui.download(content, filename=clean_name)
    except Exception as exc:
        log.debug(f"Web download trigger ignored/fallback: {exc}")

    # 2. Auto-open in Microsoft Excel
    auto_opened = False
    if auto_open:
        try:
            auto_opened = open_file_externally(target_path)
        except Exception as exc:
            log.warning(f"Auto-open failed: {exc}")

    # 3. Notification & Dialog
    if show_modal:
        show_delivery_modal(target_path, title, auto_opened=auto_opened)
    else:
        ui.notify(f"تم حفظ الملف في التنزيلات: {target_path.name}", type="positive")

    return target_path
