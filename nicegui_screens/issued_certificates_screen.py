# =============================================================================
# nicegui_screens/issued_certificates_screen.py — Issued Certificates Registry
# =============================================================================

import io
import csv
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from nicegui import ui
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
)

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


def format_template_display(raw_tmpl: str) -> str:
    """Formats raw template filename or key into a clean, compact label."""
    if not raw_tmpl:
        return "وثيقة"
    return get_short_template_badge(raw_tmpl)


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

        self.container = ui.column().classes("w-full max-w-full gap-3 p-0")
        self.show_view()

    def show_view(self) -> None:
        self.container.clear()
        with self.container:
            with UI.card().classes("w-full max-w-full p-3.5 gap-2.5"):
                # ── 1. Top Header Row ─────────────────────────────────────────
                with ui.row().classes(
                    "w-full justify-between items-center pb-2 border-b border-[var(--border-default)] app-card-header shrink-0 flex-wrap gap-2"
                ):
                    with ui.row().classes("items-center gap-2.5"):
                        ui.icon("fact_check", size="sm").classes("app-text-accent")
                        ui.label("سجل الوثائق الصادرة — Issued Certificates").classes(
                            "text-base font-bold app-text-primary"
                        )
                        self.count_badge = ui.label("0 وثيقة").classes(
                            "px-2.5 py-0.5 rounded-lg bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 font-bold text-xs border border-blue-300 dark:border-blue-700"
                        )

                    with ui.row().classes("items-center gap-2 shrink-0"):
                        # Export CSV button
                        UI.success_button(
                            "تصدير CSV / Export",
                            icon="file_download",
                            on_click=self._export_csv
                        ).classes("text-xs px-3 py-1.5")

                        # Refresh button
                        UI.secondary_button(
                            "تحديث / Refresh",
                            icon="refresh",
                            on_click=self.load_data
                        ).classes("text-xs px-3 py-1.5")

                # ── 2. Filters Toolbar (ALL CONTROLS IN ONE COMPACT ROW) ──────
                dept_options = {0: "كل الأقسام"}
                try:
                    depts = self.dept_repo.get_all() or []
                    for d in depts:
                        d_id = d.get("id") or d.get("department_id")
                        d_name = d.get("name_ar") or d.get("dept_name_ar") or f"Dept {d_id}"
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

                with ui.row().classes(
                    "w-full items-center gap-2 flex-nowrap p-1.5 rounded-xl border border-[var(--border-default)] bg-slate-50 dark:bg-slate-900/50 shrink-0"
                ):
                    # 1. Search Input (Flexible)
                    def _on_search_change(e):
                        val = extract_event_val(e, default="")
                        self.search_text = str(val or "").strip()
                        self.current_offset = 0
                        self.load_data()

                    self.search_input = ui.input(
                        placeholder="بحث بالرقم أو اسم الطالب...",
                        on_change=_on_search_change
                    ).classes(
                        "app-input rounded-xl text-xs flex-1 min-w-[140px]"
                    ).props('outlined dense clearable')

                    # 2. Department Select
                    def _on_dept_change(e):
                        val = extract_event_val(e, default=0)
                        try:
                            self.selected_dept_id = int(val) if int(val) != 0 else None
                        except Exception:
                            self.selected_dept_id = None
                        self.current_offset = 0
                        self.load_data()

                    self.dept_select = ui.select(
                        options=dept_options,
                        label="القسم",
                        value=0,
                        on_change=_on_dept_change
                    ).classes(
                        "app-input rounded-xl text-xs w-36 shrink-0"
                    ).props("outlined dense options-dense")

                    # 3. Graduation Year Select
                    def _on_year_change(e):
                        val = extract_event_val(e, default=0)
                        try:
                            self.selected_year = int(val) if int(val) != 0 else None
                        except Exception:
                            self.selected_year = None
                        self.current_offset = 0
                        self.load_data()

                    self.year_select = ui.select(
                        options=year_options,
                        label="السنة",
                        value=0,
                        on_change=_on_year_change
                    ).classes(
                        "app-input rounded-xl text-xs w-28 shrink-0"
                    ).props("outlined dense options-dense")

                    # 4. Study Type Select
                    def _on_study_change(e):
                        val = extract_event_val(e, default="all")
                        self.selected_study_type = str(val or "all")
                        self.current_offset = 0
                        self.load_data()

                    self.study_select = ui.select(
                        options=STUDY_TYPE_OPTIONS,
                        label="الدراسة",
                        value="all",
                        on_change=_on_study_change
                    ).classes(
                        "app-input rounded-xl text-xs w-28 shrink-0"
                    ).props("outlined dense options-dense")

                    # 5. Template Type Select
                    def _on_template_change(e):
                        val = extract_event_val(e, default="all")
                        self.selected_template = str(val or "all")
                        self.current_offset = 0
                        self.load_data()

                    self.tmpl_select = ui.select(
                        options=get_template_filter_options(),
                        label="النموذج",
                        value="all",
                        on_change=_on_template_change
                    ).classes(
                        "app-input rounded-xl text-xs w-48 shrink-0"
                    ).props("outlined dense options-dense")

                    # 6. Reset Filters Button (Compact icon button)
                    ui.button(
                        icon="filter_alt_off",
                        color=None,
                        on_click=self._reset_filters
                    ).classes(
                        "app-btn-secondary p-2 rounded-xl text-xs shrink-0 shadow-none"
                    ).tooltip("مسح الفلاتر / Reset Filters")

                # ── 3. Main Data Table (100% Window Width, NO Horizontal Scroll) ─
                columns = [
                    {
                        "name": "certificate_number",
                        "label": "الرقم / No",
                        "field": "certificate_number",
                        "align": "center",
                        "headerClasses": "text-center w-20",
                        "sortable": True,
                    },
                    {
                        "name": "student_name",
                        "label": "الطالب / Student",
                        "field": "student_name_ar",
                        "align": "right",
                        "sortable": True,
                    },
                    {
                        "name": "student_id",
                        "label": "ID",
                        "field": "student_id",
                        "align": "center",
                        "headerClasses": "text-center w-14",
                        "sortable": True,
                    },
                    {
                        "name": "department_name",
                        "label": "القسم / Dept",
                        "field": "department_name_ar",
                        "align": "right",
                        "headerClasses": "text-right w-24",
                        "sortable": True,
                    },
                    {
                        "name": "graduation_year",
                        "label": "السنة / Year",
                        "field": "graduation_year",
                        "align": "center",
                        "headerClasses": "text-center w-14",
                        "sortable": True,
                    },
                    {
                        "name": "study_type",
                        "label": "الدراسة",
                        "field": "study_day_type",
                        "align": "center",
                        "headerClasses": "text-center w-14",
                        "sortable": True,
                    },
                    {
                        "name": "template_type",
                        "label": "النموذج / Template",
                        "field": "template_type_display",
                        "align": "center",
                        "headerClasses": "text-center w-24",
                        "sortable": True,
                    },
                    {
                        "name": "to_title",
                        "label": "الجهة / To",
                        "field": "to_title",
                        "align": "right",
                        "headerClasses": "text-right w-20",
                        "sortable": True,
                    },
                    {
                        "name": "issue_date",
                        "label": "التاريخ / Date",
                        "field": "issue_date",
                        "align": "center",
                        "headerClasses": "text-center w-20",
                        "sortable": True,
                    },
                    {
                        "name": "actions",
                        "label": "",
                        "field": "actions",
                        "align": "center",
                        "headerClasses": "text-center w-16",
                    },
                ]

                with ui.column().classes("w-full max-w-full min-h-0"):
                    self.table = ui.table(
                        columns=columns,
                        rows=[],
                        row_key="certificate_id"
                    ).classes(Styles.TABLE_CLASSES).classes("w-full").props("flat bordered dense hide-bottom")

                    # Slot: Certificate Number badge
                    self.table.add_slot(
                        "body-cell-certificate_number",
                        """
                        <q-td :props="props">
                            <div class="row items-center justify-center">
                                <span class="px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-400 font-mono text-xs font-bold">
                                    {{ props.row.certificate_number || '—' }}
                                </span>
                            </div>
                        </q-td>
                        """
                    )

                    # Slot: Stacked Student Name (Arabic + English)
                    self.table.add_slot(
                        "body-cell-student_name",
                        """
                        <q-td :props="props">
                            <div class="flex flex-col text-right leading-tight py-0.5">
                                <span class="font-bold app-text-primary text-xs">{{ props.row.student_name_ar }}</span>
                                <span v-if="props.row.student_name_en" class="text-[10px] app-text-muted font-mono" dir="ltr">{{ props.row.student_name_en }}</span>
                            </div>
                        </q-td>
                        """
                    )

                    # Slot: Template Type badge (Compact label with tooltip)
                    self.table.add_slot(
                        "body-cell-template_type",
                        """
                        <q-td :props="props">
                            <div class="row items-center justify-center">
                                <span class="px-1.5 py-0.5 rounded text-[11px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700 truncate inline-block max-w-[110px]" :title="props.row.raw_template_type">
                                    {{ props.row.template_type_display }}
                                </span>
                            </div>
                        </q-td>
                        """
                    )

                    # Slot: To Title (Truncated if long)
                    self.table.add_slot(
                        "body-cell-to_title",
                        """
                        <q-td :props="props">
                            <span class="text-xs truncate inline-block max-w-[100px]" :title="props.row.to_title">
                                {{ props.row.to_title }}
                            </span>
                        </q-td>
                        """
                    )

                    # Slot: Actions (Edit + Delete buttons)
                    self.table.add_slot(
                        "body-cell-actions",
                        """
                        <q-td :props="props">
                            <div class="row items-center justify-center gap-1 no-wrap">
                                <q-btn size="sm" flat round dense color="primary" icon="edit" title="تعديل القيد / Edit" @click="$parent.$emit('edit_cert', props.row)">
                                    <q-tooltip class="bg-indigo-700 text-white font-bold">تعديل قيد الوثيقة / Edit Record</q-tooltip>
                                </q-btn>
                                <q-btn size="sm" flat round dense color="negative" icon="delete" title="حذف القيد / Delete" @click="$parent.$emit('delete_cert', props.row)">
                                    <q-tooltip class="bg-rose-700 text-white font-bold">حذف قيد الوثيقة / Delete Record</q-tooltip>
                                </q-btn>
                            </div>
                        </q-td>
                        """
                    )

                    self.table.on("delete_cert", self._on_delete_clicked)
                    self.table.on("edit_cert", self._on_edit_clicked)

                # ── 4. Pagination Footer ──────────────────────────────────────
                with ui.row().classes(
                    "w-full items-center justify-between mt-1 px-2 py-1 border-t border-[var(--border-default)] shrink-0"
                ):
                    with ui.row().classes("items-center gap-3"):
                        self.page_info_label = ui.label("الصفحة 1").classes(
                            "text-xs font-semibold app-text-primary"
                        )

                        # Rows per page selector
                        def _on_limit_change(e):
                            val = extract_event_val(e, default=25)
                            try:
                                self.current_limit = int(val or 25)
                            except Exception:
                                self.current_limit = 25
                            self.current_offset = 0
                            self._update_table_view()

                        ui.select(
                            options={25: "25 صف", 50: "50 صف", 100: "100 صف"},
                            value=self.current_limit,
                            on_change=_on_limit_change
                        ).classes(
                            "app-input rounded-xl text-xs w-22"
                        ).props("outlined dense options-dense")

                    with ui.row().classes("items-center gap-1.5"):
                        self.prev_btn = UI.primary_button(
                            "السابق",
                            icon="chevron_right",
                            on_click=self._prev_page
                        ).props("dense outlined").classes("text-xs px-2.5 py-1")

                        self.next_btn = UI.primary_button(
                            "التالي",
                            icon="chevron_left",
                            on_click=self._next_page
                        ).props("dense outlined").classes("text-xs px-2.5 py-1")

        # Initial data fetch
        self.load_data()

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

    def load_data(self) -> None:
        """Fetches certificate report from repository applying active search and filter parameters."""
        try:
            records = self.cert_repo.get_report(
                dept_id=self.selected_dept_id,
                graduation_year=self.selected_year,
                study_system_id=None,
                search_text=self.search_text
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

            self.all_records = records
            self._update_table_view()
        except Exception as ex:
            log.error(f"Failed to load issued certificates: {ex}")
            ui.notify(f"خطأ في تحميل سجل الوثائق: {ex}", type="negative")

    def _update_table_view(self) -> None:
        """Formats records for ui.table and updates pagination slice."""
        total_count = len(self.all_records)
        if self.count_badge:
            self.count_badge.set_text(f"{total_count} وثيقة صادرة")

        # Slice current page
        start_idx = self.current_offset
        end_idx = start_idx + self.current_limit
        page_slice = self.all_records[start_idx:end_idx]

        mapped_rows = []
        for r in page_slice:
            cert_id = r.get("certificate_id") or r.get("id") or 0
            cert_num = r.get("certificate_number") or "—"
            name_ar = r.get("student_name_ar") or r.get("full_name_ar") or "—"
            name_en = r.get("student_name_en") or r.get("full_name_en") or ""
            student_id = r.get("student_id") or "—"
            dept_name = (
                r.get("department_name_ar")
                or r.get("department_name")
                or r.get("dept_name_ar")
                or "—"
            )
            grad_year = r.get("graduation_year")
            grad_year_display = str(grad_year) if grad_year and int(grad_year) > 0 else "—"

            raw_study = str(r.get("study_day_type") or "").strip().lower()
            if raw_study == "morning":
                study_display = "صباحي"
            elif raw_study == "evening":
                study_display = "مسائي"
            else:
                study_display = raw_study or "—"

            raw_tmpl = str(r.get("template_type") or "graduation")
            tmpl_display = format_template_display(raw_tmpl)

            to_title = r.get("to_title") or "من يهمه الأمر"
            issue_date = r.get("issue_date") or "—"

            mapped_rows.append({
                "certificate_id": cert_id,
                "id": cert_id,
                "certificate_number": cert_num,
                "student_name_ar": name_ar,
                "student_name_en": name_en,
                "student_id": student_id,
                "department_name_ar": dept_name,
                "graduation_year": grad_year_display,
                "study_day_type": study_display,
                "template_type_display": tmpl_display,
                "raw_template_type": raw_tmpl,
                "to_title": to_title,
                "issue_date": issue_date,
            })

        self.records = mapped_rows
        if self.table:
            self.table.rows = mapped_rows
            self.table.update()

        # Update pagination controls
        current_page = (self.current_offset // self.current_limit) + 1
        total_pages = max(1, (total_count + self.current_limit - 1) // self.current_limit)
        if self.page_info_label:
            self.page_info_label.set_text(
                f"الصفحة {current_page} من {total_pages} | الإجمالي: {total_count} وثيقة"
            )

        if self.prev_btn:
            if self.current_offset == 0:
                self.prev_btn.disable()
            else:
                self.prev_btn.enable()

        if self.next_btn:
            if end_idx >= total_count:
                self.next_btn.disable()
            else:
                self.next_btn.enable()

    def _prev_page(self) -> None:
        self.current_offset = max(0, self.current_offset - self.current_limit)
        self._update_table_view()

    def _next_page(self) -> None:
        if self.current_offset + self.current_limit < len(self.all_records):
            self.current_offset += self.current_limit
            self._update_table_view()

    def _reset_filters(self) -> None:
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
            self.tmpl_select.options = get_template_filter_options()
            self.tmpl_select.value = "all"

        self.load_data()

    def _on_edit_clicked(self, msg) -> None:
        """Triggered when the edit button is clicked on a table row."""
        row_data = getattr(msg, "args", {}) or {}
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
                tmpl_options[k] = d

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
                        ui.label("تعديل قيد الوثيقة الصادرة / Edit Issued Certificate").classes(
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
                    label="رقم الوثيقة / Certificate Number",
                    value=current_num,
                    placeholder="مثال: 420/44 أو 105"
                ).classes("w-full app-input text-xs").props("outlined dense")

                to_input = ui.input(
                    label="الجهة المعنية / To Title",
                    value=current_to or "من يهمه الأمر",
                    placeholder="مثال: من يهمه الأمر / وزارة التعليم العالي"
                ).classes("w-full app-input text-xs").props("outlined dense")

                tmpl_input = ui.select(
                    label="نموذج الوثيقة / Certificate Template",
                    options=tmpl_options,
                    value=selected_key
                ).classes("w-full app-input text-xs").props("outlined dense options-dense")

                date_input = ui.input(
                    label="تاريخ الإصدار / Issue Date (YYYY-MM-DD)",
                    value=current_date
                ).classes("w-full app-input text-xs").props("outlined dense")

            with ui.row().classes("w-full justify-end gap-2.5 mt-2 pt-2 border-t border-[var(--border-default)]"):
                UI.secondary_button("إلغاء / Cancel", on_click=dlg.close).classes("text-xs px-3 py-1.5")

                def _confirm_save():
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
                        self.load_data()
                    except Exception as err:
                        log.error(f"Failed to update issued cert {cert_id}: {err}")
                        ui.notify(f"خطأ أثناء تعديل بيانات الوثيقة: {err}", type="negative")

                UI.primary_button(
                    "حفظ التعديلات / Save Changes",
                    icon="save",
                    on_click=_confirm_save
                ).classes("text-xs px-3 py-1.5")

        dlg.open()

    def _on_delete_clicked(self, msg) -> None:
        """Triggered when the delete button is clicked on a table row."""
        row_data = getattr(msg, "args", {}) or {}
        if not isinstance(row_data, dict):
            return

        cert_id = row_data.get("certificate_id") or row_data.get("id")
        cert_num = row_data.get("certificate_number") or "بدون رقم"
        student_name = row_data.get("student_name_ar") or ""

        if not cert_id:
            ui.notify("معرف الوثيقة غير صالح للحذف", type="negative")
            return

        with ui.dialog() as dlg, UI.card().classes(
            "p-5 gap-4 w-[420px] max-w-full rounded-2xl border border-rose-500/30 shadow-2xl bg-[var(--surface-card)]"
        ):
            with ui.row().classes("items-center gap-2.5"):
                ui.icon("warning", size="md").classes("text-rose-500")
                ui.label("تأكيد حذف قيد الوثيقة / Confirm Delete").classes(
                    "text-base font-bold text-rose-500"
                )

            with ui.column().classes("gap-2 w-full"):
                ui.label(
                    f"هل أنت متأكد من حذف قيد الوثيقة رقم ({cert_num}) الصادرة للطالب ({student_name})؟"
                ).classes("text-sm font-semibold app-text-primary leading-relaxed")

                ui.label(
                    "⚠️ تنبيه هام: سيتم حذف هذا السجل نهائياً من سجل الوثائق الصادرة، ولا يمكن التراجع عن هذه العملية."
                ).classes(
                    "text-xs text-rose-400 bg-rose-50 dark:bg-rose-950/40 p-2.5 rounded-xl border border-rose-200 dark:border-rose-900 leading-relaxed font-medium"
                )

            with ui.row().classes("w-full justify-end gap-2.5 mt-1"):
                UI.secondary_button("إلغاء / Cancel", on_click=dlg.close).classes(
                    "text-xs px-3 py-1.5"
                )

                def _confirm_delete():
                    dlg.close()
                    try:
                        self.cert_repo.delete(cert_id)
                        ui.notify(
                            f"تم حذف قيد الوثيقة رقم ({cert_num}) بنجاح",
                            type="positive"
                        )
                        self.load_data()
                    except Exception as err:
                        log.error(f"Failed to delete issued cert {cert_id}: {err}")
                        ui.notify(f"خطأ أثناء حذف قيد الوثيقة: {err}", type="negative")

                UI.danger_button(
                    "تأكيد الحذف / Confirm Delete",
                    icon="delete",
                    on_click=_confirm_delete
                ).classes("text-xs px-3 py-1.5")

        dlg.open()

    def _export_csv(self) -> None:
        """Exports the active filtered records list as an Excel-compatible CSV file."""
        if not self.all_records:
            ui.notify("لا توجد بيانات متاحة للتصدير / No records to export", type="warning")
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
            ui.download(csv_bytes, filename=filename)
            ui.notify("تم تصدير التقرير بنجاح / Report exported successfully", type="positive")
        except Exception as ex:
            log.error(f"Failed to export CSV report: {ex}")
            ui.notify(f"خطأ أثناء تصدير التقرير: {ex}", type="negative")
