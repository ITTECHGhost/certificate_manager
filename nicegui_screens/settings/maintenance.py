# =============================================================================
# nicegui_screens/settings/maintenance.py — Settings: database maintenance, backup, restore
# =============================================================================

from datetime import datetime
from nicegui import ui
import api_client
from api_config import get_api_url
from nicegui_ui.ui_components import UI
from utils.file_delivery import deliver_file


class MaintenanceMixin:
    """Database & sync tiles, backup, restore, replicas, cache, diagnostics (part of SettingsScreen)."""

    def _section_database_maintenance(self) -> None:
        """Section for Database Management, SQLite Replica Info, Offline Queue Sync, and Backups."""
        with UI.card():
            UI.card_header("إدارة وقواعد البيانات والمزامنة — Database Management & Sync", "storage", icon_css="stat-text-amber")

            # 1. Live Offline Queue & Database Replicas Overview
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)] mb-2"):
                with ui.column().classes("gap-1"):
                    ui.label("حالة قاعدة البيانات والمزامنة الأوفلاين / Database & Sync Status").classes("text-sm font-bold app-text-primary")

                    # Live metrics from SQLite (refreshed after sync / retry / discard / clear cache)
                    self._sync_status_label = ui.label("").classes("text-xs app-text-muted font-mono")
                    self._refresh_sync_status()

                from sync_engine import is_online
                UI.status_badge(online=is_online())

            # 2. Database Action Tiles Grid
            with ui.grid(columns=2).classes("w-full gap-4 mt-2"):
                UI.action_tile(
                    "مزامنة البيانات المعلقة / Sync Offline Queue",
                    "رفع السجلات التي تمت إضافتها أوفلاين إلى قاعدة بيانات MySQL",
                    "مزامنة السجلات / Sync Queue",
                    "cloud_upload", btn_variant="success", on_click_fn=self._do_sync_offline_queue
                )
                UI.action_tile(
                    "سجلات فشلت مزامنتها / Failed Sync Records",
                    "عرض السجلات التي رفضها السيرفر وإعادة المحاولة أو حذفها",
                    "عرض السجلات / Review Failed",
                    "sync_problem", btn_variant="danger", on_click_fn=self._show_failed_sync_rows
                )
                UI.action_tile(
                    "تنزيل نسخ الجداول / Download Fresh Replicas",
                    "سحب تحديثات الجداول الحالية من MySQL وحفظها في SQLite",
                    "تحديث الجداول / Pull Replicas",
                    "cloud_download", btn_variant="primary", on_click_fn=self._do_pull_mysql_replicas
                )
                UI.action_tile(
                    "مسح الذاكرة المؤقتة / Clear Read Cache",
                    "تفريغ ذاكرة الاستعلامات المحفوظة محلياً",
                    "تفريغ الذاكرة / Clear Cache",
                    "cleaning_services", btn_variant="warning", on_click_fn=self._do_clear_read_cache
                )
                UI.action_tile(
                    "فحص اتصال قاعدة البيانات / DB Diagnostics",
                    "اختبار سرعة وصحة الاتصال بقاعدة البيانات والسيرفر",
                    "فحص الاتصال / Run Test",
                    "find_in_page", btn_variant="info", on_click_fn=self._do_check_db_diagnostics
                )
                UI.action_tile(
                    "نسخ احتياطي لقاعدة البيانات / Backup Database",
                    "إنشاء نسخة SQL احتياطية حفظاً للبيانات",
                    "إنشاء نسخة / Create Backup",
                    "backup", btn_variant="success", on_click_fn=self._do_backup
                )
                UI.action_tile(
                    "استعادة نسخة احتياطية / Restore Database",
                    "استرجاع البيانات من ملف .sql سابق",
                    "استعادة النسخة / Restore Backup",
                    "restore", btn_variant="warning", on_click_fn=self._do_restore
                )
                UI.action_tile(
                    "مسح سجل التغييرات / Clear Audit Logs",
                    "تفريغ ملف سجل النشاطات الحالية",
                    "مسح السجل / Clear Logs",
                    "delete_forever", btn_variant="danger", on_click_fn=self._do_clear_logs
                )

    async def _do_backup(self) -> None:
        """Ask the server to dump the database (mysqldump runs on the server) and save the .sql to Downloads."""
        from nicegui import run
        from sync_engine import is_online
        if not is_online():
            ui.notify("النسخ الاحتياطي يتطلب الاتصال بالسيرفر / Backup requires a server connection.", type="warning")
            return
        ui.notify("جاري إنشاء النسخة الاحتياطية... / Creating backup...", type="info")
        try:
            resp = await run.io_bound(
                api_client.get, f"{get_api_url()}/admin/backup",
                params={"personnel_id": self.emp_id}, timeout=300.0
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            filename = f"certificate_manager_backup_{datetime.now():%Y%m%d_%H%M%S}.sql"
            deliver_file(resp.content, filename, title="تم إنشاء النسخة الاحتياطية بنجاح / Backup created", auto_open=False)
        except Exception as exc:
            ui.notify(f"Backup failed: {exc}", type="negative")

    def _do_restore(self) -> None:
        """Pick a .sql backup, confirm, then upload it to the server, which restores it (admin only)."""
        from sync_engine import is_online
        if not is_online():
            ui.notify("الاستعادة تتطلب الاتصال بالسيرفر / Restore requires a server connection.", type="warning")
            return

        picked: dict = {}
        with ui.dialog() as dialog, UI.card():
            UI.card_header("استعادة نسخة احتياطية / Restore Database", "restore", icon_css="stat-text-amber")
            ui.label(
                "تحذير: الاستعادة تستبدل جميع البيانات الحالية في قاعدة البيانات. "
                "Warning: restoring replaces ALL current data in the database."
            ).classes("text-sm font-bold text-red-500")
            status_label = ui.label("لم يتم اختيار ملف بعد / No file selected").classes("text-xs app-text-muted")

            async def _on_pick(e):
                name = e.file.name or ""
                if not name.lower().endswith(".sql"):
                    ui.notify("يجب اختيار ملف .sql / Please choose a .sql file.", type="warning")
                    return
                picked["name"] = name
                picked["content"] = await e.file.read()
                status_label.set_text(f"{name} ({round(len(picked['content']) / 1024, 1)} KB)")

            ui.upload(label="اختر ملف النسخة الاحتياطية (.sql)", auto_upload=True, on_upload=_on_pick) \
                .props("accept=.sql max-files=1").classes("w-full")

            async def _confirm_restore():
                from nicegui import run
                if not picked.get("content"):
                    ui.notify("يرجى اختيار ملف أولاً / Please choose a file first.", type="warning")
                    return
                dialog.close()
                ui.notify("جاري الاستعادة... / Restoring...", type="info")
                try:
                    resp = await run.io_bound(
                        api_client.post, f"{get_api_url()}/admin/restore",
                        params={"personnel_id": self.emp_id},
                        files={"file": (picked["name"], picked["content"], "application/sql")},
                        timeout=600.0,
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                    ui.notify("تمت استعادة قاعدة البيانات / Database restored!", type="positive")
                except Exception as exc:
                    ui.notify(f"Restore failed: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat")
                ui.button("استعادة / Restore", icon="restore", on_click=_confirm_restore).props("color=negative")
        dialog.open()

    def _do_pull_mysql_replicas(self) -> None:
        """Triggers manual download of fresh table replicas from MySQL to SQLite."""
        from sync_engine import is_online, pull_mysql_to_sqlite
        if not is_online():
            ui.notify("لا يوجد اتصال بالسيرفر حالياً لتنزيل الجداول.", type="warning")
            return
        try:
            pull_mysql_to_sqlite(force_full=True)
            ui.notify("تم تحديث وتنزيل نسخ الجداول الحديثة بنجاح! / Fresh table replicas downloaded!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء تنزيل الجداول: {exc}", type="negative")

    def _do_clear_read_cache(self) -> None:
        """Clears SQLite read_cache entries."""
        try:
            from sync_engine import get_local_connection
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM read_cache")
            conn.commit()
            cursor.close()
            conn.close()
            self._refresh_sync_status()
            ui.notify("تم تفريغ الذاكرة المؤقتة بنجاح! / Read cache cleared!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء مسح الذاكرة: {exc}", type="negative")

    def _do_check_db_diagnostics(self) -> None:
        """Performs live database diagnostic checks."""
        from sync_engine import is_online
        try:
            from sync_engine import sqlite_read_one
            status = "Online (MySQL + SQLite)" if is_online() else "Offline (SQLite Replica)"
            q_res = sqlite_read_one("SELECT COUNT(*) AS cnt FROM sync_queue WHERE COALESCE(status, 'pending') = 'pending'")
            q_cnt = q_res.get("cnt", 0) if q_res else 0
            ui.notify(
                f"فحص قاعدة البيانات:\n• الحالة: {status}\n• المعلق للمزامنة: {q_cnt} عنصر",
                type="info"
            )
        except Exception as exc:
            ui.notify(f"فحص قاعدة البيانات فشل: {exc}", type="negative")
