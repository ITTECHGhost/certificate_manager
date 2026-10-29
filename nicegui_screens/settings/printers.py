# =============================================================================
# nicegui_screens/settings/printers.py — Settings: printers and hardware setup
# =============================================================================

import os
import json
import logging
from nicegui import ui
import app_paths
from nicegui_ui.ui_components import UI

log = logging.getLogger(__name__)


class PrintersMixin:
    """Printer selection, test page, Windows default printer (part of SettingsScreen)."""

    # ─────────────────────────────────────────────────────────────────────────
    # Printers & Hardware Setup Section (Replaces legacy Profile & Account tab)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_printer_config(self) -> dict:
        """Loads persistent printer setup from config/printer_config.json."""
        from nicegui_screens.certificate_screen import get_default_printer
        config_path = str(app_paths.data_path("config", "printer_config.json"))
        def_p = get_default_printer()
        default_cfg = {
            "cert_printer": def_p,
            "report_printer": def_p,
            "paper_size": "A4",
            "orientation": "Portrait",
            "auto_print": False,
            "copies": 1
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def _save_printer_config_file(self, cfg: dict) -> bool:
        """Saves printer setup to config/printer_config.json."""
        config_path = str(app_paths.data_path("config", "printer_config.json"))
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            log.error(f"Error saving printer config: {e}")
            return False

    def _send_printer_test_page(self, printer_name: str) -> tuple[bool, str]:
        """Sends a formatted Windows GDI test page directly to the specified printer."""
        try:
            import win32ui
            import win32con
            from datetime import datetime

            dc = win32ui.CreateDC()
            dc.CreatePrinterDC(printer_name)
            dc.StartDoc("Certificate Manager Test Page")
            dc.StartPage()

            font_title = win32ui.CreateFont({
                "name": "Segoe UI",
                "height": 55,
                "weight": win32con.FW_BOLD
            })
            dc.SelectObject(font_title)
            dc.TextOut(120, 120, "Certificate Manager — Printer Test Page")

            font_body = win32ui.CreateFont({
                "name": "Segoe UI",
                "height": 35,
                "weight": win32con.FW_NORMAL
            })
            dc.SelectObject(font_body)
            dc.TextOut(120, 220, f"Target Printer: {printer_name}")
            dc.TextOut(120, 280, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            dc.TextOut(120, 340, "Status: Printer communication test PASSED successfully.")
            dc.TextOut(120, 400, "Institution: College of Computer Science & Information Technology")
            dc.TextOut(120, 460, "System: Certificate Manager (NiceGUI Enterprise Suite)")

            dc.EndPage()
            dc.EndDoc()
            dc.DeleteDC()
            return True, "Success"
        except Exception as exc:
            return False, str(exc)

    def _section_printer_settings(self) -> None:
        """
        Renders the dedicated Printer Setup & Hardware Configuration View.
        Configures certificate printer, reports printer, page size, orientation,
        and provides direct test printing and setting Windows default printer.
        """
        from nicegui_screens.certificate_screen import get_installed_printers, get_default_printer

        installed_printers = get_installed_printers()
        default_win_printer = get_default_printer()
        cfg = self._load_printer_config()

        cur_cert_printer = cfg.get("cert_printer") or default_win_printer
        if cur_cert_printer not in installed_printers and installed_printers:
            cur_cert_printer = default_win_printer if default_win_printer in installed_printers else installed_printers[0]

        cur_report_printer = cfg.get("report_printer") or default_win_printer
        if cur_report_printer not in installed_printers and installed_printers:
            cur_report_printer = default_win_printer if default_win_printer in installed_printers else installed_printers[0]

        cur_paper = cfg.get("paper_size", "A4")
        if cur_paper not in ["A4", "Letter", "A3", "Legal"]:
            cur_paper = "A4"

        cur_orientation = cfg.get("orientation", "Portrait")
        if cur_orientation not in ["Portrait", "Landscape"]:
            cur_orientation = "Portrait"

        cur_auto_print = bool(cfg.get("auto_print", False))
        cur_copies = int(cfg.get("copies", 1))

        with UI.card().classes("w-full p-6 gap-6"):
            UI.card_header("إعداد وتهيئة الطابعات — Printer & Hardware Setup", "print", icon_css="stat-text-blue")

            # Status Banner & Current Default
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    with ui.element("div").classes("w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center shrink-0"):
                        ui.icon("print", size="md").classes("text-blue-400")
                    with ui.column().classes("gap-0"):
                        ui.label("إدارة وتوجيه الطابعات المادية والافتراضية").classes("font-bold text-sm app-text-primary")
                        ui.label(f"الطابعة الافتراضية في Windows حالياً: {default_win_printer}").classes("text-xs app-text-muted font-mono")

                with ui.row().classes("items-center gap-2"):
                    ui.label(f"عدد الطابعات المكتشفة: {len(installed_printers)}").classes("text-xs font-semibold px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20")

            # Form Fields Grid
            with ui.grid(columns=2).classes("w-full gap-5"):
                # 1. Certificate Printer
                cert_printer_select = UI.select(
                    "طابعة الوثائق والشهادات / Certificate Printer",
                    options={p: p for p in installed_printers},
                    value=cur_cert_printer
                ).classes("w-full")

                # 2. Report Printer
                report_printer_select = UI.select(
                    "طابعة التقارير والجداول / Reports & Lists Printer",
                    options={p: p for p in installed_printers},
                    value=cur_report_printer
                ).classes("w-full")

                # 3. Paper Size
                paper_size_select = UI.select(
                    "حجم الورق الافتراضي / Default Paper Size",
                    options=["A4", "Letter", "A3", "Legal"],
                    value=cur_paper
                ).classes("w-full")

                # 4. Orientation
                orientation_select = UI.select(
                    "اتجاه الطباعة / Print Orientation",
                    options=["Portrait", "Landscape"],
                    value=cur_orientation
                ).classes("w-full")

                # 5. Default Copies
                copies_input = UI.number_input(
                    "عدد النسخ الافتراضي / Default Copies",
                    value=cur_copies, min=1, max=10
                ).classes("w-full")

            # Automation & Options
            with ui.row().classes("app-tile w-full items-center justify-between p-4 rounded-xl border border-[var(--border-default)] mt-2"):
                with ui.column().classes("gap-0.5"):
                    ui.label("طباعة فورية تلقائية / Auto-print immediately").classes("text-sm font-bold app-text-primary")
                    ui.label("إرسال الوثيقة للطباعة فور اكتمال توليدها دون طلب تأكيد يدوي").classes("text-xs app-text-muted")
                auto_print_switch = UI.switch("", value=cur_auto_print)

            # Action Buttons Row
            with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] flex-wrap gap-3"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    # Test Print Button
                    def do_test_print():
                        target_p = cert_printer_select.value
                        if not target_p:
                            UI.notify("الرجاء اختيار طابعة للفحص أولاً", type="warning")
                            return
                        success, msg = self._send_printer_test_page(target_p)
                        if success:
                            UI.notify(f"تم إرسال صفحة الفحص بنجاح إلى ({target_p})", type="positive")
                        else:
                            UI.notify(f"تعذر إرسال صفحة الفحص: {msg}", type="negative")

                    UI.secondary_button(
                        "طباعة صفحة فحص / Test Print",
                        icon="receipt_long",
                        on_click=do_test_print
                    ).classes("text-xs")

                    # Set Windows Default
                    def do_set_win_default():
                        target_p = cert_printer_select.value
                        if not target_p:
                            UI.notify("الرجاء اختيار طابعة أولاً", type="warning")
                            return
                        try:
                            import win32print
                            win32print.SetDefaultPrinter(target_p)
                            UI.notify(f"تم تعيين ({target_p}) كطابعة افتراضية للنظام بنجاح!", type="positive")
                        except Exception as ex:
                            UI.notify(f"فشل تعيين الطابعة الافتراضية: {ex}", type="negative")

                    UI.secondary_button(
                        "تعيين كافتراضية في النظام / Set as Windows Default",
                        icon="star",
                        on_click=do_set_win_default
                    ).classes("text-xs")

                # Save Configuration Button
                def do_save_printer_cfg():
                    new_cfg = {
                        "cert_printer": cert_printer_select.value or "",
                        "report_printer": report_printer_select.value or "",
                        "paper_size": paper_size_select.value or "A4",
                        "orientation": orientation_select.value or "Portrait",
                        "auto_print": bool(auto_print_switch.value),
                        "copies": int(copies_input.value or 1)
                    }
                    if self._save_printer_config_file(new_cfg):
                        UI.notify("تم حفظ إعدادات الطابعات بنجاح!", type="positive")
                    else:
                        UI.notify("فشل حفظ إعدادات الطابعات!", type="negative")

                UI.success_button(
                    "حفظ إعدادات الطابعات / Save Printer Settings",
                    icon="save",
                    on_click=do_save_printer_cfg
                ).classes("text-sm px-6 py-2.5 font-bold shadow-md")
