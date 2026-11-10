# =============================================================================
# nicegui_screens/settings/server.py — Settings: server/API config and the offline sync queue
# =============================================================================

import json
import os
from nicegui import ui
from nicegui_ui.ui_components import UI


_SYNC_KIND_LABELS = {
    "students": "طالب",
    "academic_periods": "فصل دراسي",
    "enrollments": "درجة مادة",
    "issued_certificates": "وثيقة",
    "study_routines": "سيرة دراسية",
    "study_routine_courses": "مادة سيرة دراسية",
    "study_routine_period": "فصل سيرة دراسية",
    "study_routine_period_courses": "مادة فصل سيرة دراسية",
}


def _summarize_sync_payload(table_name: str | None, payload_text: str | None) -> str:
    """Turn a queued offline record (JSON) into a short readable line."""
    try:
        p = json.loads(payload_text or "{}")
    except Exception:
        return str(payload_text or "")[:120]
    if table_name == "enrollments":
        return f"الفصل {p.get('period_id')} · المادة {p.get('course_id')} · الدرجة {p.get('score')} · الدور {p.get('passed_round')}"
    if table_name == "academic_periods":
        return f"الطالب {p.get('student_id')} · {p.get('academic_year')} · المرحلة {p.get('stage_number')} · الفصل {p.get('semester_num')}"
    if table_name == "students":
        return f"{p.get('full_name_ar') or ''} · القسم {p.get('department_id')}"
    if table_name == "issued_certificates":
        return f"الطالب {p.get('student_id')} · رقم الوثيقة {p.get('certificate_number')} · {p.get('issue_date')}"
    return ", ".join(f"{k}={v}" for k, v in p.items() if k != "id")[:160]


def _friendly_sync_reason(error_text: str | None) -> str:
    """Explain a server sync error in plain words (Arabic / English)."""
    err = str(error_text or "")
    if "Conflict:" in err or "changed on the server" in err:
        return "تعارض: تم تعديل السجل على السيرفر بعد نسخة هذا الجهاز. تجاهل يبقي نسخة السيرفر، تجاوز يحفظ نسخة هذا الجهاز"
    if "Possible duplicate" in err:
        dup = err.split("Possible duplicate:", 1)[-1].strip()
        return f"طالب مكرر محتمل: {dup}. تجاهل إن كان الشخص نفسه، تجاوز لإضافته كطالب جديد"
    if "1452" in err:
        return "السجل المرتبط (مثل الفصل الدراسي) غير موجود في قاعدة البيانات الرئيسية"
    if "Parent record was not synced" in err:
        return "السجل الأب لم تتم مزامنته"
    if "1062" in err:
        return "السجل موجود مسبقاً (مكرر)"
    if "1048" in err or "cannot be null" in err.lower():
        return "حقل مطلوب فارغ"
    if "Unsupported table" in err:
        return "نوع سجل غير مدعوم للمزامنة"
    return err.replace("Database synchronization failed: ", "")[:200] or "خطأ غير معروف"


class ServerMixin:
    """Server host/port/secret settings and the offline sync queue (part of SettingsScreen)."""

    def _section_server_config(self) -> None:
        """Section for configuring Server API Host, Port, Secret Key, and Auto Reconnect settings."""
        with UI.card():
            UI.card_header("إعدادات السيرفر والشبكة", "dns", icon_css="stat-text-blue")

            from api_config import load_server_config
            cfg = load_server_config()

            api_host = f"http://{cfg.get('host', '127.0.0.1')}"
            api_port = str(cfg.get('port', 2030))
            api_secret = cfg.get('secret', 'certificate_manager_secret_key')
            api_timeout = int(cfg.get('timeout', 5))
            auto_sync = bool(cfg.get('auto_sync', True))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.server_host_input = UI.text_input(
                    "عنوان السيرفر",
                    value=api_host,
                    placeholder="http://127.0.0.1"
                )
                self.server_port_input = UI.text_input(
                    "منفذ السيرفر",
                    value=api_port,
                    placeholder="2030"
                )
                self.api_secret_input = UI.text_input(
                    "مفتاح التطبيق السرّي",
                    value=api_secret,
                    placeholder="المفتاح السري"
                )
                self.api_timeout_input = UI.number_input(
                    "مهلة الاتصال (بالثواني)",
                    value=api_timeout, min=1, max=60
                )

            with ui.row().classes("app-tile w-full items-center justify-between p-3.5 rounded-xl border mt-2"):
                with ui.column().classes("gap-0"):
                    UI.standard_label("المزامنة التلقائية عند الاتصال")
                    UI.muted_label("تفعيل المزامنة الفورية للبيانات المحفوظة أوفلاين بمجرد توفر الاتصال بالسيرفر.")
                self.auto_sync_switch = UI.switch("تفعيل", value=auto_sync)

            with ui.row().classes("w-full justify-between items-center pt-2 border-t mt-3"):
                UI.secondary_button(
                    "فحص الاتصال بالسيرفر",
                    icon="wifi_tethering",
                    on_click=self._test_server_connection
                )
                UI.success_button(
                    "حفظ إعدادات السيرفر",
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
                ui.notify(f"الاتصال بالسيرفر {full_url} يعمل بنجاح!", type="positive")
            else:
                ui.notify(f"السيرفر {full_url} غير متصل حالياً. يعمل التطبيق دون اتصال.", type="warning")
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

            ui.notify(f"تم حفظ إعدادات السيرفر والمنفذ ({cfg['api_url']}) محلياً بنجاح", type="positive")
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
                    f"تمت مزامنة {result.get('synced', 0)} سجل، وفشل {result['failed']} — راجع السجلات الفاشلة.",
                    type="warning"
                )
            else:
                ui.notify("تمت مزامنة البيانات المعلقة مع قاعدة البيانات بنجاح!", type="positive")
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
            ui.notify("لا توجد سجلات فاشلة", type="positive")
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
            UI.card_header(f"سجلات فشلت مزامنتها ({len(failed_rows)})", "sync_problem", icon_css="stat-text-amber")
            ui.label(
                "هذه السجلات أُنشئت أوفلاين ورفضها السيرفر. الحذف يزيلها من هذا الجهاز فقط ولا يمس قاعدة البيانات الرئيسية. "
                "هذه السجلات أُنشئت دون اتصال ورفضها السيرفر. التجاهل يحذفها من هذا الجهاز فقط."
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
                    {"name": "kind", "label": "النوع", "field": "kind", "align": "left", "style": "width: 150px"},
                    {"name": "record", "label": "السجل", "field": "record", "align": "left"},
                    {"name": "reason", "label": "السبب", "field": "reason", "align": "left"},
                    {"name": "created_at", "label": "أُنشئ", "field": "created_at", "align": "left", "style": "width: 160px"},
                ],
                rows=view_rows,
                row_key="id",
                pagination=10,
            ).props("flat dense wrap-cells").classes("w-full text-xs")

            def _retry_all():
                count = retry_failed_queue_rows()
                dialog.close()
                self._refresh_sync_status()
                ui.notify(f"سيعاد إرسال {count} سجل في المزامنة القادمة", type="info")

            def _override_all():
                with ui.dialog() as confirm, UI.card():
                    ui.label(
                        "إعادة الإرسال مع تجاوز فحص التعارض والتكرار؟ سيتم حفظ نسخة هذا الجهاز فوق تعديلات السيرفر، "
                        "وحفظ الطلاب المكررين المحتملين كطلاب جدد."
                    ).classes("text-sm font-bold")

                    def _do_override():
                        count = retry_failed_queue_rows(override=True)
                        confirm.close()
                        dialog.close()
                        self._refresh_sync_status()
                        ui.notify(f"سيعاد إرسال {count} سجل مع التجاوز", type="info")

                    with ui.row().classes("w-full justify-end gap-2 pt-2"):
                        ui.button("إلغاء", on_click=confirm.close).props("flat")
                        ui.button("تجاوز وإرسال", icon="published_with_changes", on_click=_do_override).props("color=warning")
                confirm.open()

            def _discard_all():
                with ui.dialog() as confirm, UI.card():
                    ui.label(
                        f"حذف {len(failed_rows)} سجل نهائياً من هذا الجهاز؟"
                    ).classes("text-sm font-bold")

                    def _do_discard():
                        count = discard_failed_queue_rows()
                        confirm.close()
                        dialog.close()
                        self._refresh_sync_status()
                        ui.notify(f"تم حذف {count} سجل.", type="positive")

                    with ui.row().classes("w-full justify-end gap-2 pt-2"):
                        ui.button("إلغاء", on_click=confirm.close).props("flat")
                        ui.button("حذف", icon="delete_forever", on_click=_do_discard).props("color=negative")
                confirm.open()

            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("إغلاق", on_click=dialog.close).props("flat")
                ui.button("إعادة المحاولة", icon="replay", on_click=_retry_all).props("color=primary")
                ui.button("إعادة مع التجاوز", icon="published_with_changes", on_click=_override_all).props("color=warning")
                ui.button("حذف الكل", icon="delete_forever", on_click=_discard_all).props("color=negative")
        dialog.open()

    def _section_server_update(self) -> None:
        """Admins: upload CertificateManagerUpdate-x.y.z.zip and choose when the server installs it."""
        import tempfile
        from datetime import datetime, timedelta
        from nicegui import run
        import services.server_update as su
        from nicegui_ui.upload_utils import read_upload

        state = {"zip": None, "name": ""}

        with UI.card():
            UI.card_header("تحديث الخادم", "system_update", icon_css="stat-text-blue")
            UI.muted_label("ارفع ملف التحديث المضغوط الذي جهّزه المطوّر واختر وقت التثبيت. "
                           "يأخذ الخادم نسخة احتياطية من قاعدة البيانات أولاً، ويعود إلى الإصدار السابق إن فشل التحديث.")

            @ui.refreshable
            def _status_view():
                lines = su.describe(state.get("status"))
                with ui.column().classes("gap-1"):
                    ui.label(f"إصدار الخادم: {lines['version']}").classes("app-text-primary font-semibold")
                    for key in ("pending", "last"):
                        if lines[key]:
                            ui.label(lines[key]).classes("app-caption")
                    if lines["warning"]:
                        ui.label(lines["warning"]).classes("app-chip app-chip--warning")
                    last = (state.get("status") or {}).get("last") or {}
                    if last.get("state") == "failed" and last.get("log_tail"):
                        with ui.expansion("سجل آخر محاولة").classes("w-full"):
                            ui.label("\n".join(last["log_tail"])).classes("app-caption whitespace-pre-wrap").style("direction:ltr")

            async def _refresh():
                state["status"] = await run.io_bound(su.get_status)
                _status_view.refresh()

            _status_view()

            file_label = ui.label("لم يتم اختيار ملف التحديث").classes("text-xs app-text-muted italic")

            async def _on_upload(e):
                name, content = await read_upload(e)
                if not name.lower().endswith(".zip"):
                    ui.notify("اختر ملف التحديث المضغوط", type="warning")
                    return
                path = os.path.join(tempfile.gettempdir(), name)
                with open(path, "wb") as f:
                    f.write(content)
                state["zip"], state["name"] = path, name
                file_label.set_text(f"الملف: {name} ({round(len(content) / 1048576, 1)} MB)")

            ui.upload(label="اختر ملف التحديث المضغوط", auto_upload=True, on_upload=_on_upload) \
                .props("accept=.zip max-files=1").classes("w-full")

            default_time = (datetime.now() + timedelta(days=1)).replace(hour=22, minute=0) \
                if datetime.now().hour >= 22 else datetime.now().replace(hour=22, minute=0)
            with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                when = ui.radio({"now": "الآن", "later": "في وقت محدد"}, value="later").props("inline")
                when_at = ui.input("وقت التثبيت", value=default_time.strftime("%Y-%m-%d %H:%M")) \
                    .props("outlined dense").classes("w-48")
                when_at.bind_visibility_from(when, "value", value="later")
            UI.muted_label("في وقت التثبيت يتوقف الخادم دقيقة تقريباً: اختر وقتاً لا يُصدر فيه أحد وثائق.")

            def _ask_password(title: str, on_ok):
                with ui.dialog() as dlg, UI.card().classes("w-[420px] max-w-full gap-3"):
                    UI.card_header(title, "lock")
                    pw = ui.input("كلمة المرور", password=True, password_toggle_button=True).props("outlined dense autofocus")

                    async def _go():
                        dlg.close()
                        await on_ok(pw.value or "")
                    pw.on("keydown.enter", _go)
                    with ui.row().classes("app-dialog-actions"):
                        UI.ghost_button("إلغاء", on_click=dlg.close)
                        UI.primary_button("متابعة", icon="check", on_click=_go)
                dlg.open()

            async def _send(password: str):
                run_at = "now"
                if when.value == "later":
                    try:
                        run_at = datetime.strptime((when_at.value or "").strip(), "%Y-%m-%d %H:%M").strftime("%Y-%m-%dT%H:%M")
                    except ValueError:
                        ui.notify("اكتب الوقت بالشكل 2026-11-10 22:00", type="warning")
                        return
                n = ui.notification("جاري رفع التحديث إلى الخادم...", timeout=None, spinner=True)
                ok, msg, pending = await run.io_bound(su.upload, state["zip"], self.session.username, password, run_at)
                n.dismiss()
                if ok:
                    ui.notify(f"سيُثبت الإصدار {pending['version']} في {pending['run_at'].replace('T', ' ')}", type="positive")
                else:
                    ui.notify(msg or "تعذر رفع التحديث", type="negative", timeout=8000)
                await _refresh()

            async def _cancel(password: str):
                ok, msg = await run.io_bound(su.cancel, self.session.username, password)
                ui.notify("أُلغي التحديث المنتظر" if ok else (msg or "تعذر الإلغاء"), type="positive" if ok else "negative")
                await _refresh()

            def _start_upload():
                if not state["zip"]:
                    ui.notify("اختر ملف التحديث أولاً", type="warning")
                    return
                _ask_password("تأكيد رفع التحديث", _send)

            with ui.row().classes("w-full justify-end gap-2"):
                UI.ghost_button("تحديث الحالة", on_click=_refresh)
                UI.ghost_button("إلغاء التحديث المنتظر", on_click=lambda: _ask_password("تأكيد الإلغاء", _cancel))
                UI.primary_button("رفع وجدولة التحديث", icon="cloud_upload", on_click=_start_upload)

            ui.timer(0.1, _refresh, once=True)
