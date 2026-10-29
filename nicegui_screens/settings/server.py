# =============================================================================
# nicegui_screens/settings/server.py — Settings: server/API config and the offline sync queue
# =============================================================================

import json
from nicegui import ui
from nicegui_ui.ui_components import UI


_SYNC_KIND_LABELS = {
    "students": "طالب / Student",
    "academic_periods": "فصل دراسي / Semester",
    "enrollments": "درجة مادة / Course grade",
    "issued_certificates": "وثيقة / Certificate",
    "study_routines": "روتين / Routine",
    "study_routine_courses": "مادة روتين / Routine course",
    "study_routine_period": "فصل روتين / Routine period",
    "study_routine_period_courses": "مادة فصل روتين / Routine period course",
}


def _summarize_sync_payload(table_name: str | None, payload_text: str | None) -> str:
    """Turn a queued offline record (JSON) into a short readable line."""
    try:
        p = json.loads(payload_text or "{}")
    except Exception:
        return str(payload_text or "")[:120]
    if table_name == "enrollments":
        return (f"الفصل {p.get('period_id')} · المادة {p.get('course_id')} · الدرجة {p.get('score')} · الدور {p.get('passed_round')}"
                f"  —  Period {p.get('period_id')}, course {p.get('course_id')}, score {p.get('score')}")
    if table_name == "academic_periods":
        return (f"الطالب {p.get('student_id')} · {p.get('academic_year')} · المرحلة {p.get('stage_number')} · الفصل {p.get('semester_num')}"
                f"  —  Student {p.get('student_id')}, stage {p.get('stage_number')}, semester {p.get('semester_num')}")
    if table_name == "students":
        return f"{p.get('full_name_ar') or ''} / {p.get('full_name_en') or ''} · القسم {p.get('department_id')}"
    if table_name == "issued_certificates":
        return f"الطالب {p.get('student_id')} · رقم الوثيقة {p.get('certificate_number')} · {p.get('issue_date')}"
    return ", ".join(f"{k}={v}" for k, v in p.items() if k != "id")[:160]


def _friendly_sync_reason(error_text: str | None) -> str:
    """Explain a server sync error in plain words (Arabic / English)."""
    err = str(error_text or "")
    if "Conflict:" in err or "changed on the server" in err:
        return ("تعارض: تم تعديل السجل على السيرفر بعد نسخة هذا الجهاز / Conflict: the record was changed on the server "
                "after this laptop's copy — Discard keeps the server version, Override saves this laptop's version")
    if "Possible duplicate" in err:
        dup = err.split("Possible duplicate:", 1)[-1].strip()
        return (f"طالب مكرر محتمل: {dup} / Possible duplicate student: {dup} — "
                "Discard if it is the same person, Override to keep it as a new student")
    if "1452" in err:
        return "السجل المرتبط (مثل الفصل الدراسي) غير موجود في قاعدة البيانات الرئيسية / Linked record (e.g. the semester) does not exist on the server"
    if "Parent record was not synced" in err:
        return "السجل الأب لم تتم مزامنته / Its parent record failed to sync"
    if "1062" in err:
        return "السجل موجود مسبقاً (مكرر) / Duplicate: the record already exists on the server"
    if "1048" in err or "cannot be null" in err.lower():
        return "حقل مطلوب فارغ / A required field is empty"
    if "Unsupported table" in err:
        return "نوع سجل غير مدعوم للمزامنة / Record type not supported by sync"
    return err.replace("Database synchronization failed: ", "")[:200] or "خطأ غير معروف / Unknown error"


class ServerMixin:
    """Server host/port/secret settings and the offline sync queue (part of SettingsScreen)."""

    def _section_server_config(self) -> None:
        """Section for configuring Server API Host, Port, Secret Key, and Auto Reconnect settings."""
        with UI.card():
            UI.card_header("إعدادات السيرفر والشبكة — Server & API Settings", "dns", icon_css="stat-text-blue")

            from api_config import load_server_config
            cfg = load_server_config()

            api_host = f"http://{cfg.get('host', '127.0.0.1')}"
            api_port = str(cfg.get('port', 2030))
            api_secret = cfg.get('secret', 'certificate_manager_secret_key')
            api_timeout = int(cfg.get('timeout', 5))
            auto_sync = bool(cfg.get('auto_sync', True))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.server_host_input = UI.text_input(
                    "عنوان السيرفر / Server Host (IP/Domain)",
                    value=api_host,
                    placeholder="http://127.0.0.1"
                )
                self.server_port_input = UI.text_input(
                    "منفذ السيرفر / Server Port",
                    value=api_port,
                    placeholder="2030"
                )
                self.api_secret_input = UI.text_input(
                    "مفتاح التطبيق السرّي / App Secret Key",
                    value=api_secret,
                    placeholder="Secret Key..."
                )
                self.api_timeout_input = UI.number_input(
                    "مهلة الاتصال (بالثواني) / Request Timeout (s)",
                    value=api_timeout, min=1, max=60
                )

            with ui.row().classes("app-tile w-full items-center justify-between p-3.5 rounded-xl border mt-2"):
                with ui.column().classes("gap-0"):
                    UI.standard_label("المزامنة التلقائية عند الاتصال / Auto Online Reconnection Sync")
                    UI.muted_label("تفعيل المزامنة الفورية للبيانات المحفوظة أوفلاين بمجرد توفر الاتصال بالسيرفر.")
                self.auto_sync_switch = UI.switch("تفعيل / Enable", value=auto_sync)

            with ui.row().classes("w-full justify-between items-center pt-2 border-t mt-3"):
                UI.secondary_button(
                    "فحص الاتصال بالسيرفر / Test Connection",
                    icon="wifi_tethering",
                    on_click=self._test_server_connection
                )
                UI.success_button(
                    "حفظ إعدادات السيرفر / Save Server Config",
                    icon="save",
                    on_click=self._save_server_config
                )

    def _test_server_connection(self) -> None:
        """Tests live reachability of the configured Server API host & port."""
        from sync_engine import check_network_status
        host = (self.server_host_input.value if hasattr(self, 'server_host_input') and self.server_host_input else "127.0.0.1")
        port = (self.server_port_input.value if hasattr(self, 'server_port_input') and self.server_port_input else "2030")
        clean_host = str(host).replace("http://", "").replace("https://", "").strip().rstrip("/")
        full_url = f"http://{clean_host}:{port}"

        try:
            online = check_network_status(target_url=full_url)
            if online:
                ui.notify(f"الاتصال بالسيرفر {full_url} يعمل بنجاح! / Server connected successfully!", type="positive")
            else:
                ui.notify(f"السيرفر {full_url} غير متصل حالياً. يعمل التطبيق في الوضع المحتجز (Offline Mode).", type="warning")
        except Exception as exc:
            ui.notify(f"فحص الاتصال فشل: {exc}", type="negative")

    def _save_server_config(self) -> None:
        """Saves Server API settings locally to server_config.json."""
        from api_config import save_server_config
        from sync_engine import check_network_status, set_online
        host = (self.server_host_input.value if hasattr(self, 'server_host_input') and self.server_host_input else "127.0.0.1")
        port = (self.server_port_input.value if hasattr(self, 'server_port_input') and self.server_port_input else "2030")
        secret = (self.api_secret_input.value if hasattr(self, 'api_secret_input') and self.api_secret_input else "certificate_manager_secret_key")
        timeout = (self.api_timeout_input.value if hasattr(self, 'api_timeout_input') and self.api_timeout_input else 5)
        auto_sync = (self.auto_sync_switch.value if hasattr(self, 'auto_sync_switch') and self.auto_sync_switch else True)

        try:
            cfg = save_server_config(host=host, port=port, secret=secret, timeout=timeout, auto_sync=auto_sync)
            # Update active repository instances with the new URL
            if hasattr(self, 's_repo') and self.s_repo:
                self.s_repo.api_url = cfg["api_url"]
            if hasattr(self, 'student_repo') and self.student_repo:
                self.student_repo.api_url = cfg["api_url"]
                self.student_repo.api_base_url = cfg["api_url"]

            # Re-evaluate network status for the new URL immediately
            set_online(check_network_status(target_url=cfg["api_url"]))

            ui.notify(f"تم حفظ إعدادات السيرفر والمنفذ ({cfg['api_url']}) محلياً في server_config.json بنجاح!", type="positive")
            self._test_server_connection()
        except Exception as exc:
            ui.notify(f"خطأ أثناء حفظ إعدادات السيرفر: {exc}", type="negative")

    def _do_sync_offline_queue(self) -> None:
        """Triggers manual sync of queued offline INSERTs to MySQL."""
        from sync_engine import is_online, sync_offline_queue_to_mysql
        if not is_online():
            ui.notify("لا يوجد اتصال بالسيرفر حالياً للمزامنة. يرجى الاتصال أولاً.", type="warning")
            return
        try:
            result = sync_offline_queue_to_mysql()
            self._refresh_sync_status()
            if result.get("failed"):
                ui.notify(
                    f"تمت مزامنة {result.get('synced', 0)} سجل، وفشل {result['failed']} — راجع السجلات الفاشلة. "
                    f"/ Synced {result.get('synced', 0)}, failed {result['failed']} — see Failed Sync Records.",
                    type="warning"
                )
            else:
                ui.notify("تمت مزامنة البيانات المعلقة مع قاعدة البيانات بنجاح! / Offline queue synced!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء المزامنة: {exc}", type="negative")

    def _refresh_sync_status(self) -> None:
        """Re-read pending / failed / cache counts from SQLite into the status line."""
        label = getattr(self, "_sync_status_label", None)
        if label is None:
            return
        queue_count = failed_count = cache_count = 0
        try:
            from sync_engine import sqlite_read_one, get_queue_status
            q_status = get_queue_status()
            queue_count = q_status.get("pending", 0)
            failed_count = q_status.get("failed", 0)
            c_res = sqlite_read_one("SELECT COUNT(*) AS cnt FROM read_cache")
            cache_count = c_res.get("cnt", 0) if c_res else 0
        except Exception:
            pass
        label.set_text(
            f"سجلات معلقة للمزامنة: {queue_count}  |  فشلت مزامنتها: {failed_count}  |  عناصر الذاكرة المؤقتة: {cache_count}"
        )

    def _show_failed_sync_rows(self) -> None:
        """List queue rows the server rejected, with Retry / Discard actions."""
        from sync_engine import get_queue_status, retry_failed_queue_rows, discard_failed_queue_rows
        failed_rows = [r for r in get_queue_status().get("entries", []) if r.get("status") == "failed"]
        if not failed_rows:
            ui.notify("لا توجد سجلات فاشلة / No failed sync records.", type="positive")
            return

        view_rows = [
            {
                "id": r["id"],
                "kind": _SYNC_KIND_LABELS.get(r.get("table_name"), r.get("table_name")),
                "created_at": str(r.get("created_at") or ""),
                "record": _summarize_sync_payload(r.get("table_name"), r.get("payload")),
                "reason": _friendly_sync_reason(r.get("last_error")),
            }
            for r in failed_rows
        ]
        reason_counts: dict = {}
        for v in view_rows:
            reason_counts[v["reason"]] = reason_counts.get(v["reason"], 0) + 1

        with ui.dialog() as dialog, UI.card().style("width: min(92vw, 1100px); max-width: 92vw"):
            UI.card_header(f"سجلات فشلت مزامنتها ({len(failed_rows)}) / Failed Sync Records", "sync_problem", icon_css="stat-text-amber")
            ui.label(
                "هذه السجلات أُنشئت أوفلاين ورفضها السيرفر. الحذف يزيلها من هذا الجهاز فقط ولا يمس قاعدة البيانات الرئيسية. "
                "These records were created offline and rejected by the server. Discarding removes them from this PC only."
            ).classes("text-xs app-text-muted")

            # Summary: how many rows fail for each reason
            with ui.column().classes("w-full gap-1 p-3 rounded-xl border border-[var(--border-default)]"):
                for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(str(cnt)).props("color=negative")
                        ui.label(reason).classes("text-sm app-text-primary")

            ui.table(
                columns=[
                    {"name": "id", "label": "#", "field": "id", "align": "left", "style": "width: 60px"},
                    {"name": "kind", "label": "النوع / Type", "field": "kind", "align": "left", "style": "width: 150px"},
                    {"name": "record", "label": "السجل / Record", "field": "record", "align": "left"},
                    {"name": "reason", "label": "السبب / Reason", "field": "reason", "align": "left"},
                    {"name": "created_at", "label": "أُنشئ / Created", "field": "created_at", "align": "left", "style": "width: 160px"},
                ],
                rows=view_rows,
                row_key="id",
                pagination=10,
            ).props("flat dense wrap-cells").classes("w-full text-xs")

            def _retry_all():
                count = retry_failed_queue_rows()
                dialog.close()
                self._refresh_sync_status()
                ui.notify(f"سيعاد إرسال {count} سجل في المزامنة القادمة / {count} record(s) will be sent at the next sync.", type="info")

            def _override_all():
                with ui.dialog() as confirm, UI.card():
                    ui.label(
                        "إعادة الإرسال مع تجاوز فحص التعارض والتكرار؟ سيتم حفظ نسخة هذا الجهاز فوق تعديلات السيرفر، "
                        "وحفظ الطلاب المكررين المحتملين كطلاب جدد. / Send again WITHOUT the conflict and duplicate "
                        "checks? This laptop's version overwrites changes made on the server, and possible duplicate "
                        "students are saved as new students."
                    ).classes("text-sm font-bold")

                    def _do_override():
                        count = retry_failed_queue_rows(override=True)
                        confirm.close()
                        dialog.close()
                        self._refresh_sync_status()
                        ui.notify(f"سيعاد إرسال {count} سجل مع التجاوز / {count} record(s) will be sent with override.", type="info")

                    with ui.row().classes("w-full justify-end gap-2 pt-2"):
                        ui.button("إلغاء / Cancel", on_click=confirm.close).props("flat")
                        ui.button("تجاوز وإرسال / Override", icon="published_with_changes", on_click=_do_override).props("color=warning")
                confirm.open()

            def _discard_all():
                with ui.dialog() as confirm, UI.card():
                    ui.label(
                        f"حذف {len(failed_rows)} سجل نهائياً من هذا الجهاز؟ / Permanently discard {len(failed_rows)} record(s) from this PC?"
                    ).classes("text-sm font-bold")

                    def _do_discard():
                        count = discard_failed_queue_rows()
                        confirm.close()
                        dialog.close()
                        self._refresh_sync_status()
                        ui.notify(f"تم حذف {count} سجل / Discarded {count} record(s).", type="positive")

                    with ui.row().classes("w-full justify-end gap-2 pt-2"):
                        ui.button("إلغاء / Cancel", on_click=confirm.close).props("flat")
                        ui.button("حذف / Discard", icon="delete_forever", on_click=_do_discard).props("color=negative")
                confirm.open()

            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("إغلاق / Close", on_click=dialog.close).props("flat")
                ui.button("إعادة المحاولة / Retry All", icon="replay", on_click=_retry_all).props("color=primary")
                ui.button("إعادة مع التجاوز / Override", icon="published_with_changes", on_click=_override_all).props("color=warning")
                ui.button("حذف الكل / Discard All", icon="delete_forever", on_click=_discard_all).props("color=negative")
        dialog.open()
