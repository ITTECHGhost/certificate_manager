# =============================================================================
# nicegui_screens/settings/logs_analytics.py — Settings: activity log and analytics
# =============================================================================

from nicegui import ui
import app_paths
from nicegui_ui.ui_components import UI


class LogsAnalyticsMixin:
    """System activity log viewer, analytics summary, audit-log clearing (part of SettingsScreen)."""

    def _section_system_logs(self) -> None:
        with UI.card():
            UI.card_header("سجلات حركة النظام — System Activity Logs", "terminal", icon_css="stat-text-amber")
            log_file = app_paths.data_path("logs", "system_log.txt")
            log_content = ""
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        log_content = "".join(lines[-100:])
                except Exception:
                    log_content = "تعذر قراءة ملف السجلات / Could not read log file"
            else:
                log_content = "لا يوجد سجل نشاطات حالياً / No activity log file found"

            ui.textarea(value=log_content).classes("w-full h-48 font-mono text-xs bg-[var(--bg-main)] rounded-xl p-3").props("readonly")

    def _section_analytics(self) -> None:
        with UI.card():
            UI.card_header("تحليلات وإحصائيات النظام — Analytics Summary", "analytics", icon_css="stat-text-purple")
            with ui.grid(columns=4).classes("w-full gap-4"):
                UI.stat_card("إجمالي السجلات", "Total DB Records", "1,250+", "storage", variant="blue")
                UI.stat_card("الوثائق المصدرة", "Issued Certificates", "340+", "description", variant="emerald")
                UI.stat_card("المستخدمين النشطين", "Active System Users", "12", "people", variant="amber")
                UI.stat_card("حالة مزامنة SQLite", "Sync Engine Status", "100%", "cloud_done", variant="purple")

    def _do_clear_logs(self) -> None:
        try:
            self.s_repo.clear_audit_logs()
            ui.notify("تم مسح سجل التغييرات / Audit logs cleared!", type="info")
        except Exception as exc:
            ui.notify(f"Clear logs failed: {exc}", type="negative")
