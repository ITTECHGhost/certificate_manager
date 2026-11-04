# =============================================================================
# nicegui_screens/issued_certificates_screen.py — Issued Certificates Registry
# =============================================================================

import io
import os
import re
import csv
import urllib.parse
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from nicegui import run, ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles
from data.repositories import (
    IssuedCertificateRepository,
    DepartmentRepository,
    StudySystemRepository,
)
from nicegui_ui.template_constants import (
    get_short_template_badge,
    get_friendly_template_name,
    get_template_filter_options,
    load_templates_config,
    get_template_label_ar,
)
from utils.file_delivery import deliver_file
import app_paths

log = logging.getLogger(__name__)

TEMPLATE_FILTER_OPTIONS = get_template_filter_options()

STUDY_TYPE_OPTIONS = {
    "all": "كل الدراسات",
    "morning": "صباحي",
    "evening": "مسائي",
}


def extract_event_val(e, default=None):
    """Safely extracts value from NiceGUI event object or raw value."""
    if isinstance(e, (int, float, str, bool)):
        return e
    if hasattr(e, "value") and not isinstance(e.value, property):
        try:
            return e.value
        except Exception:
            return default
    if hasattr(e, "args"):
        args = e.args
        if isinstance(args, (int, float, str, bool)):
            return args
        if isinstance(args, dict) and "value" in args:
            return args["value"]
    return default


def template_filter_options_ar() -> dict:
    """Filter keys stay the standard names the matcher uses; the labels are Arabic."""
    return {k: (v if k == "all" else get_template_label_ar(k)) for k, v in get_template_filter_options().items()}


def sort_newest_first(records: list[dict]) -> list[dict]:
    """Latest issue date first; the higher record id breaks ties (same order online and offline)."""
    def key(r):
        cid = r.get("certificate_id") or r.get("id") or 0
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            cid = 0
        return (str(r.get("issue_date") or ""), cid)
    return sorted(records, key=key, reverse=True)


def find_issued_files(certificate_number) -> tuple[str | None, str | None]:
    """The saved Word file of an issued certificate (and its PDF, if made), found by the
    number that leads its file name; (None, None) when this computer does not have it."""
    num = str(certificate_number or "").strip()
    if not num or num == "—":
        return None, None
    safe_num = re.sub(r'[\\/*?:"<>|]', "-", num).strip()
    folder = str(app_paths.data_path("certificates"))
    try:
        names = [n for n in os.listdir(folder) if n.lower().endswith(".docx") and n.startswith(safe_num + " - ")]
    except OSError:
        return None, None
    if not names:
        return None, None
    docx = max((os.path.join(folder, n) for n in names), key=os.path.getmtime)
    pdf = os.path.splitext(docx)[0] + ".pdf"
    return docx, (pdf if os.path.exists(pdf) else None)


def format_template_display(raw_tmpl: str) -> str:
    """Formats raw template filename or key into a clean, compact label."""
    if not raw_tmpl:
        return "وثيقة"
    return get_template_label_ar(raw_tmpl)


class IssuedCertificatesScreen:
    """
    Dedicated log and registry screen for all issued student certificates.
    Designed for 100% full-screen fit with NO horizontal scrolling:
      - Single-row compact toolbar with all filter controls.
      - Compact, dense table where all columns fit comfortably in one view.
      - Destructive deletion warning modal.
      - Excel-compatible UTF-8 BOM CSV report export.
    """

    def __init__(self, on_edit_certificate=None):
        self.on_edit_certificate = on_edit_certificate
        self.cert_repo = IssuedCertificateRepository()
        self.dept_repo = DepartmentRepository()
        self.study_repo = StudySystemRepository()

        # Filter states
        self.search_text: str = ""
        self.selected_dept_id: Optional[int] = None
        self.selected_year: Optional[int] = None
        self.selected_study_type: str = "all"
        self.selected_template: str = "all"

        # Pagination & Data
        self.current_limit: int = 25
        self.current_offset: int = 0
        self.all_records: List[Dict[str, Any]] = []
        self.records: List[Dict[str, Any]] = []

        # UI references
        self.search_input = None
        self.dept_select = None
        self.year_select = None
        self.study_select = None
        self.tmpl_select = None
        self.table = None
        self.count_badge = None
        self.page_info_label = None
        self.prev_btn = None
        self.next_btn = None
        self.loading = True

        self.container = ui.column().classes("w-full gap-4")
        self.show_view()

    def show_view(self) -> None:
        self.container.clear()
        with self.container:
            with UI.card().classes("gap-4"):
                # ── Header: count, export, refresh ───────────────────────────
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label("سجل الوثائق الصادرة").classes("app-section-title")
                    self.count_badge = UI.chip("0 وثيقة")
                    ui.space()
                    UI.icon_button("refresh", "تحديث القائمة", on_click=self.load_data)
                    UI.secondary_button("تصدير CSV", icon="file_download", on_click=self._export_csv)

                # ── Filters: one row on wide windows, wrapping on narrow ones ─
                dept_options = {0: "كل الأقسام"}
                try:
                    depts = self.dept_repo.get_all() or []
                    for d in depts:
                        d_id = d.get("id") or d.get("department_id")
                        d_name = d.get("name_ar") or d.get("dept_name_ar") or f"قسم {d_id}"
                        if d_id:
                            dept_options[int(d_id)] = d_name
                except Exception as e:
                    log.warning(f"Failed to load departments: {e}")

                year_options = {0: "كل السنوات"}
                year_set = set()
                try:
                    from sync_engine import sqlite_read_all
                    rows = sqlite_read_all(
                        "SELECT DISTINCT graduation_year FROM graduation_orders "
                        "WHERE graduation_year IS NOT NULL AND graduation_year > 0 "
                        "ORDER BY graduation_year DESC"
                    )
                    for r in rows:
                        y = r.get("graduation_year")
                        if y:
                            year_set.add(int(y))
                except Exception as ex:
                    log.debug(f"Could not load graduation years from local database: {ex}")

                if not year_set:
                    year_set = {2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017}

                for y in sorted(year_set, reverse=True):
                    year_options[y] = str(y)

                with ui.row().classes("app-filter-row w-full items-center gap-2"):
                    async def _on_search_change(e):
                        val = extract_event_val(e, default="")
                        self.search_text = str(val or "").strip()
                        self.current_offset = 0
                        await self.load_data()

                    self.search_input = UI.search_input(
                        placeholder="ابحث برقم الوثيقة أو اسم الطالب",
                        on_change=_on_search_change,
                    ).classes("flex-1 min-w-[220px]")

                    async def _on_dept_change(e):
                        val = extract_event_val(e, default=0)
                        try:
                            self.selected_dept_id = int(val) if int(val) != 0 else None
                        except Exception:
                            self.selected_dept_id = None
                        self.current_offset = 0
                        await self.load_data()

                    self.dept_select = UI.select("القسم", options=dept_options, value=0,
                                                 on_change=_on_dept_change).classes("w-52", remove="w-full")

                    async def _on_year_change(e):
                        val = extract_event_val(e, default=0)
                        try:
                            self.selected_year = int(val) if int(val) != 0 else None
                        except Exception:
                            self.selected_year = None
                        self.current_offset = 0
                        await self.load_data()

                    self.year_select = UI.select("سنة التخرج", options=year_options, value=0,
                                                 on_change=_on_year_change).classes("w-36", remove="w-full")

                    async def _on_study_change(e):
                        val = extract_event_val(e, default="all")
                        self.selected_study_type = str(val or "all")
                        self.current_offset = 0
                        await self.load_data()

                    self.study_select = UI.select("الدراسة", options=STUDY_TYPE_OPTIONS, value="all",
                                                  on_change=_on_study_change).classes("w-40", remove="w-full")

                    async def _on_template_change(e):
                        val = extract_event_val(e, default="all")
                        self.selected_template = str(val or "all")
                        self.current_offset = 0
                        await self.load_data()

                    self.tmpl_select = UI.select("نوع الوثيقة", options=template_filter_options_ar(), value="all",
                                                 on_change=_on_template_change).classes("w-56", remove="w-full")

                    UI.icon_button("filter_alt_off", "مسح عوامل التصفية", on_click=self._reset_filters)

                # ── List: a skeleton first, then the table and one paginator ─
                @ui.refreshable
                def body_view():
                    if self.loading:
                        UI.skeleton(rows=6, height=44)
                        return
                    self._build_table()

                body_view()
                self._body_view = body_view

        # Fetch after the page is on screen, so the skeleton shows at once
        ui.timer(0.01, self.load_data, once=True)

    def _build_table(self) -> None:
        total_count = len(self.all_records)
        if not total_count:
            if self._has_filters():
                UI.empty_state("لا توجد وثيقة مطابقة", "غيّر عوامل التصفية أو امسحها.", icon="search_off",
                               action_text="مسح عوامل التصفية", on_action=self._reset_filters)
            else:
                UI.empty_state("لم تصدر أي وثيقة بعد", "الوثائق التي تصدرها من شاشة إصدار الوثيقة تظهر هنا.",
                               icon="fact_check")
            return

        self.current_offset = min(self.current_offset, (total_count - 1) // self.current_limit * self.current_limit)
        page_slice = self.all_records[self.current_offset:self.current_offset + self.current_limit]
        self.records = [self._map_row(r) for r in page_slice]

        self.table = UI.data_table([
            {"name": "certificate_number", "label": "الرقم", "field": "certificate_number"},
            {"name": "student_name", "label": "الطالب", "field": "student_name_ar", "align": "right"},
            {"name": "template_type", "label": "الوثيقة", "field": "template_type_display", "align": "right", "classes": "app-cell-wrap"},
            {"name": "to_title", "label": "إلى", "field": "to_title", "align": "right", "classes": "app-cell-wrap"},
            {"name": "issue_date", "label": "تاريخ الإصدار", "field": "issue_date"},
        ], self.records, row_key="certificate_id", clickable=True)
        self.table.add_slot("body-cell-certificate_number", """
            <q-td :props="props"><span class="font-semibold app-text-primary" dir="ltr">{{ props.value }}</span></q-td>
        """)
        self.table.add_slot("body-cell-student_name", """
            <q-td :props="props">
                <div class="flex flex-col text-right leading-tight">
                    <span class="font-semibold app-text-primary">{{ props.row.student_name_ar }}</span>
                    <span v-if="props.row.student_name_en" class="app-caption" dir="ltr">{{ props.row.student_name_en }}</span>
                </div>
            </q-td>
        """)
        self.table.on("rowClick", lambda e: self._show_cert_detail(e.args[1]))

        UI.paginator(total_count, self.current_offset // self.current_limit + 1, self.current_limit, self._go_to_page)

    def _go_to_page(self, page: int) -> None:
        self.current_offset = max(0, (int(page) - 1) * self.current_limit)
        self._update_table_view()

    def _has_filters(self) -> bool:
        return bool(self.search_text or self.selected_dept_id or self.selected_year
                    or self.selected_study_type != "all" or self.selected_template != "all")

    @staticmethod
    def _matches_template(raw_tmpl: str, filter_key: str) -> bool:
        """Determines if a certificate's template_type matches the selected filter key."""
        if not filter_key or filter_key == "all":
            return True
        badge = get_short_template_badge(raw_tmpl)
        if badge == filter_key:
            return True
        raw = str(raw_tmpl or "").lower().strip()
        key = str(filter_key or "").lower().strip()
        if key in badge.lower() or badge.lower() in key:
            return True
        if key in raw or raw in key:
            return True
        return False

    async def load_data(self) -> None:
        """Fetches the report with the active filters (newest first) and redraws the list."""
        try:
            records = await run.io_bound(
                self.cert_repo.get_report,
                dept_id=self.selected_dept_id,
                graduation_year=self.selected_year,
                study_system_id=None,
                search_text=self.search_text,
            ) or []

            # 1. Filter by template type
            if self.selected_template and self.selected_template != "all":
                records = [
                    r for r in records
                    if self._matches_template(r.get("template_type"), self.selected_template)
                ]

            # 2. Filter for study_day_type if selected
            if self.selected_study_type and self.selected_study_type != "all":
                target_type = self.selected_study_type.lower()
                records = [
                    r for r in records
                    if str(r.get("study_day_type") or "").strip().lower() == target_type
                    or (target_type == "morning" and "صباح" in str(r.get("study_day_type") or ""))
                    or (target_type == "evening" and "مساء" in str(r.get("study_day_type") or ""))
                ]

            self.all_records = sort_newest_first(records)
        except Exception as ex:
            log.error(f"Failed to load issued certificates: {ex}")
            self.all_records = []
            UI.notify(f"تعذر تحميل سجل الوثائق: {ex}. تحقق من الاتصال ثم اضغط تحديث.", type="negative")
        self.loading = False
        self._update_table_view()

    def _update_table_view(self) -> None:
        if self.count_badge:
            self.count_badge.set_text(f"{len(self.all_records)} وثيقة")
        if hasattr(self, "_body_view"):
            self._body_view.refresh()

    @staticmethod
    def _map_row(r: dict) -> dict:
        cert_id = r.get("certificate_id") or r.get("id") or 0
        grad_year = r.get("graduation_year")
        try:
            grad_year_display = str(grad_year) if grad_year and int(grad_year) > 0 else "—"
        except (TypeError, ValueError):
            grad_year_display = "—"

        raw_study = str(r.get("study_day_type") or "").strip().lower()
        study_display = {"morning": "صباحي", "evening": "مسائي"}.get(raw_study, raw_study or "—")
        raw_tmpl = str(r.get("template_type") or "graduation")

        return {
            "certificate_id": cert_id,
            "id": cert_id,
            "certificate_number": r.get("certificate_number") or "—",
            "student_name_ar": r.get("student_name_ar") or r.get("full_name_ar") or "—",
            "student_name_en": r.get("student_name_en") or r.get("full_name_en") or "",
            "student_id": r.get("student_id") or "—",
            "department_name_ar": r.get("department_name_ar") or r.get("department_name") or r.get("dept_name_ar") or "—",
            "graduation_year": grad_year_display,
            "study_day_type": study_display,
            "template_type_display": format_template_display(raw_tmpl),
            "raw_template_type": raw_tmpl,
            "to_title": r.get("to_title") or "من يهمه الأمر",
            "issue_date": r.get("issue_date") or "—",
        }

    async def _reset_filters(self) -> None:
        """Resets all filters to initial states."""
        self.search_text = ""
        self.selected_dept_id = None
        self.selected_year = None
        self.selected_study_type = "all"
        self.selected_template = "all"
        self.current_offset = 0

        if self.search_input:
            self.search_input.value = ""
        if self.dept_select:
            self.dept_select.value = 0
        if self.year_select:
            self.year_select.value = 0
        if self.study_select:
            self.study_select.value = "all"
        if self.tmpl_select:
            self.tmpl_select.options = template_filter_options_ar()
            self.tmpl_select.value = "all"

        await self.load_data()

    def _show_cert_detail(self, row: dict) -> None:
        """A clicked record: all its fields, reprint and PDF of the saved document, edit and delete."""
        if not row:
            return
        docx_path, pdf_path = find_issued_files(row.get("certificate_number"))

        with ui.dialog() as dialog, UI.card().classes("app-dialog gap-4").style("width: 600px"):
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.label(f"الوثيقة رقم {row.get('certificate_number') or '—'}").classes("app-section-title")
                ui.space()
                UI.icon_button("close", "إغلاق", on_click=dialog.close, dense=True)

            UI.dl([
                ("الطالب", row.get("student_name_ar")),
                ("القسم", row.get("department_name_ar")),
                ("الوثيقة", row.get("template_type_display")),
                ("إلى", row.get("to_title")),
                ("تاريخ الإصدار", row.get("issue_date")),
                ("سنة التخرج", row.get("graduation_year")),
                ("الدراسة", row.get("study_day_type")),
            ])

            if not docx_path:
                with ui.row().classes("app-chip--warning w-full items-start gap-2 no-wrap rounded-lg p-3"):
                    ui.icon("info", size="20px").classes("shrink-0")
                    ui.label("ملف هذه الوثيقة غير موجود على هذا الجهاز. لطباعتها افتح القيد في شاشة الإصدار وأصدرها مجددًا.").classes("text-sm")

            async def _reprint():
                dialog.close()
                await self._reprint(docx_path, pdf_path)

            async def _open_pdf():
                await self._open_pdf(docx_path, pdf_path)

            # Dialogs opened from here belong to the page: one built inside this closed dialog never shows
            def _edit():
                dialog.close()
                with self.container:
                    self._on_edit_clicked(row)

            def _delete():
                dialog.close()
                with self.container:
                    self._on_delete_clicked(row)

            with ui.row().classes("app-dialog-actions items-center"):
                UI.danger_icon_button("delete", "حذف القيد", on_click=_delete)
                ui.space()
                UI.ghost_button("تعديل القيد", icon="edit", on_click=_edit)
                pdf_btn = UI.secondary_button("ملف PDF", icon="picture_as_pdf", on_click=_open_pdf)
                print_btn = UI.primary_button("إعادة الطباعة", icon="print", on_click=_reprint)
                if not docx_path:
                    pdf_btn.disable()
                    print_btn.disable()
        dialog.open()

    @staticmethod
    async def _ensure_pdf(docx_path: str, pdf_path: str | None) -> str | None:
        if pdf_path and os.path.exists(pdf_path):
            return pdf_path
        from services.office_automation import generate_pdf_from_docx
        UI.notify("جارٍ تحويل الوثيقة إلى PDF", type="info")
        res = await run.io_bound(generate_pdf_from_docx, docx_path)
        return res if res and os.path.exists(res) else None

    async def _reprint(self, docx_path: str, pdf_path: str | None) -> None:
        """Prints the saved document again; the record itself is not touched."""
        from nicegui_screens.certificate_screen import CertificateScreen
        pdf = await self._ensure_pdf(docx_path, pdf_path)
        if pdf is None:
            UI.notify("تعذر إنشاء معاينة PDF (يتطلب Microsoft Word)؛ يمكنك الطباعة مباشرة.", type="warning")
        with self.container:
            CertificateScreen.show_in_app_print_dialog(pdf, docx_path)

    async def _open_pdf(self, docx_path: str, pdf_path: str | None) -> None:
        pdf = await self._ensure_pdf(docx_path, pdf_path)
        if pdf is None:
            UI.notify("تعذر تحويل الوثيقة إلى PDF: يتطلب Microsoft Word.", type="negative")
            return
        ui.navigate.to(f"/certificates_files/{urllib.parse.quote(os.path.basename(pdf))}?v={int(os.path.getmtime(pdf))}",
                       new_tab=True)

    def _on_edit_clicked(self, row_data: dict) -> None:
        """Opens the record in the issue screen (or, standalone, a small edit dialog)."""
        if not isinstance(row_data, dict):
            return

        if self.on_edit_certificate:
            self.on_edit_certificate(row_data)
            return

        cert_id = row_data.get("certificate_id") or row_data.get("id")
        if not cert_id:
            ui.notify("معرف الوثيقة غير صالح للتعديل", type="negative")
            return

        student_id = row_data.get("student_id")
        student_name_ar = row_data.get("student_name_ar") or ""
        student_name_en = row_data.get("student_name_en") or ""
        current_num = str(row_data.get("certificate_number") or "").strip()
        if current_num == "—":
            current_num = ""
        current_to = str(row_data.get("to_title") or "").strip()
        current_date = str(row_data.get("issue_date") or "").strip()
        if current_date == "—":
            current_date = datetime.now().strftime("%Y-%m-%d")
        current_tmpl = str(row_data.get("raw_template_type") or row_data.get("template_type") or "").strip()

        # Build options for template select: key -> display_name
        config = load_templates_config()
        tmpl_options = {}
        for k, v in config.items():
            d = v.get("display_name")
            if d:
                tmpl_options[k] = get_template_label_ar(d)

        # Resolve selected option key
        selected_key = current_tmpl
        if selected_key not in tmpl_options:
            for k, v in config.items():
                if v.get("display_name") == get_short_template_badge(current_tmpl):
                    selected_key = k
                    break
            if selected_key not in tmpl_options:
                selected_key = list(tmpl_options.keys())[0] if tmpl_options else current_tmpl

        with ui.dialog() as dlg, UI.card().classes(
            "p-5 gap-4 w-[480px] max-w-full rounded-2xl border border-blue-500/30 shadow-2xl bg-[var(--surface-card)]"
        ):
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-2.5"):
                    ui.icon("edit_document", size="md").classes("text-blue-500")
                    with ui.column().classes("gap-0"):
                        ui.label("تعديل قيد الوثيقة الصادرة").classes(
                            "text-base font-bold app-text-primary"
                        )
                        ui.label(f"معرف قيد الوثيقة: #{cert_id}").classes("text-[11px] app-text-muted font-mono")

                ui.button(icon="close", on_click=dlg.close).classes("app-btn-secondary p-1 rounded-lg text-xs")

            # Student Info Banner
            with ui.row().classes("w-full items-center justify-between p-2.5 rounded-xl bg-[var(--bg-main)] border border-[var(--border-default)]"):
                with ui.column().classes("gap-0"):
                    ui.label(student_name_ar).classes("text-xs font-bold app-text-primary")
                    if student_name_en:
                        ui.label(student_name_en).classes("text-[10px] app-text-muted font-mono")
                with ui.row().classes("items-center gap-1.5"):
                    ui.icon("person", size="xs").classes("text-slate-400")
                    ui.label(f"طالب ID: {student_id}").classes("text-xs font-mono font-semibold app-text-primary")

            # Form Inputs
            with ui.column().classes("w-full gap-3"):
                num_input = ui.input(
                    label="رقم الوثيقة",
                    value=current_num,
                    placeholder="مثال: 420/44 أو 105"
                ).classes("w-full app-input text-xs").props("outlined dense")

                to_input = ui.input(
                    label="الجهة المعنية",
                    value=current_to or "من يهمه الأمر",
                    placeholder="مثال: من يهمه الأمر / وزارة التعليم العالي"
                ).classes("w-full app-input text-xs").props("outlined dense")

                tmpl_input = ui.select(
                    label="نموذج الوثيقة",
                    options=tmpl_options,
                    value=selected_key
                ).classes("w-full app-input text-xs").props("outlined dense options-dense")

                date_input = UI.attach_date_picker(ui.input(
                    label="تاريخ الإصدار",
                    value=current_date
                ).classes("w-full app-input text-xs").props("outlined dense"))

            with ui.row().classes("w-full justify-end gap-2.5 mt-2 pt-2 border-t border-[var(--border-default)]"):
                UI.ghost_button("إلغاء", on_click=dlg.close)

                async def _confirm_save():
                    new_number = (num_input.value or "").strip()
                    new_to = (to_input.value or "").strip() or "من يهمه الأمر"
                    new_date = (date_input.value or "").strip()
                    new_tmpl = tmpl_input.value or selected_key

                    # Validate certificate number duplicate check if modified
                    if new_number and new_number != current_num and student_id:
                        dup = self.cert_repo.check_duplicate(new_number, int(student_id))
                        if dup.get("exists") and not dup.get("same_student"):
                            ui.notify(
                                f"رقم الوثيقة ({new_number}) مسجل بالفعل لطالب آخر: {dup.get('owner_name')}",
                                type="negative"
                            )
                            return

                    try:
                        self.cert_repo.update(
                            cert_id=int(cert_id),
                            to_title=new_to,
                            template_type=str(new_tmpl),
                            issue_date=new_date,
                            certificate_number=new_number or None
                        )
                        dlg.close()
                        ui.notify("تم تعديل بيانات قيد الوثيقة بنجاح", type="positive")
                        await self.load_data()
                    except Exception as err:
                        log.error(f"Failed to update issued cert {cert_id}: {err}")
                        ui.notify(f"خطأ أثناء تعديل بيانات الوثيقة: {err}", type="negative")

                UI.primary_button(
                    "حفظ التعديلات",
                    icon="save",
                    on_click=_confirm_save
                ).classes("text-xs px-3 py-1.5")

        dlg.open()

    def _on_delete_clicked(self, row_data: dict) -> None:
        """Asks before deleting a record, naming its number and student."""
        cert_id = row_data.get("certificate_id") or row_data.get("id")
        cert_num = row_data.get("certificate_number") or "بدون رقم"
        student_name = row_data.get("student_name_ar") or ""

        if not cert_id:
            UI.notify("تعذر حذف القيد: معرّفه غير معروف. حدّث القائمة وأعد المحاولة.", type="negative")
            return

        async def _confirm_delete():
            try:
                await run.io_bound(self.cert_repo.delete, cert_id)
                UI.notify(f"حُذف قيد الوثيقة رقم ({cert_num})", type="positive")
                await self.load_data()
            except Exception as err:
                log.error(f"Failed to delete issued cert {cert_id}: {err}")
                UI.notify(f"تعذر حذف قيد الوثيقة: {err}", type="negative")

        UI.confirm_dialog(
            "حذف قيد الوثيقة",
            f"سيُحذف قيد الوثيقة رقم ({cert_num}) الصادرة للطالب ({student_name}) من السجل. لا يمكن التراجع عن ذلك.",
            "حذف القيد",
            _confirm_delete,
        )

    def _export_csv(self) -> None:
        """Exports the active filtered records list as an Excel-compatible CSV file."""
        if not self.all_records:
            ui.notify("لا توجد بيانات متاحة للتصدير", type="warning")
            return

        try:
            output = io.StringIO()
            # UTF-8 with BOM for Arabic Excel support
            output.write("\ufeff")
            writer = csv.writer(output)

            # CSV Headers
            writer.writerow([
                "رقم الوثيقة",
                "معرف الطالب",
                "اسم الطالب (عربي)",
                "اسم الطالب (إنكليزي)",
                "القسم",
                "سنة التخرج",
                "نوع الدراسة",
                "نوع النموذج",
                "الجهة المعنية (إلى)",
                "تاريخ الإصدار",
            ])

            for r in self.all_records:
                cert_num = r.get("certificate_number") or ""
                st_id = r.get("student_id") or ""
                name_ar = r.get("student_name_ar") or r.get("full_name_ar") or ""
                name_en = r.get("student_name_en") or r.get("full_name_en") or ""
                dept_name = (
                    r.get("department_name_ar")
                    or r.get("department_name")
                    or r.get("dept_name_ar")
                    or ""
                )
                grad_year = r.get("graduation_year")
                grad_year_str = str(grad_year) if grad_year and int(grad_year) > 0 else ""

                raw_study = str(r.get("study_day_type") or "").strip().lower()
                study_str = "صباحي" if raw_study == "morning" else ("مسائي" if raw_study == "evening" else raw_study)

                raw_tmpl = str(r.get("template_type") or "graduation")
                tmpl_str = format_template_display(raw_tmpl)

                to_title = r.get("to_title") or "من يهمه الأمر"
                issue_date = r.get("issue_date") or ""

                writer.writerow([
                    cert_num,
                    st_id,
                    name_ar,
                    name_en,
                    dept_name,
                    grad_year_str,
                    study_str,
                    tmpl_str,
                    to_title,
                    issue_date,
                ])

            csv_bytes = output.getvalue().encode("utf-8-sig")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"issued_certificates_report_{timestamp}.csv"
            deliver_file(
                content=csv_bytes,
                filename=filename,
                title="تم تصدير وحفظ تقرير الوثائق المصدّرة بنجاح",
                auto_open=False,
                show_modal=True
            )
        except Exception as ex:
            log.error(f"Failed to export CSV report: {ex}")
            ui.notify(f"خطأ أثناء تصدير التقرير: {ex}", type="negative")
