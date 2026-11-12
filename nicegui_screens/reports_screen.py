# =============================================================================
# nicegui_screens/reports_screen.py — «تقارير الطلاب»: filters, counts, group tables, Excel export
# =============================================================================

import io
from datetime import datetime

from nicegui import ui

from nicegui_ui.ui_components import UI
from data.repositories import DepartmentRepository, StudySystemRepository
from data.repositories.reports import ReportsRepository

GROUP_OPTIONS = {
    "department": "القسم",
    "study_system": "نظام الدراسة",
    "graduation_year": "سنة التخرج",
    "semester": "الفصل",
    "admission_year": "سنة القبول",
    "status": "حالة التخرج",
    "gender": "الجنس",
    "nationality": "الجنسية",
    "order": "أمر التخرج",
}
NUMBER_COLS = [("count", "العدد"), ("male", "ذكور"), ("female", "إناث"),
               ("graduated", "متخرجون"), ("avg_average", "متوسط المعدل")]
STUDENT_COLS = [("full_name_ar", "الاسم"), ("department", "القسم"), ("study_system", "نظام الدراسة"),
                ("gender", "الجنس"), ("nationality", "الجنسية"), ("admission_year", "سنة القبول"),
                ("graduation_year", "سنة التخرج"), ("order_number", "رقم الأمر"), ("average", "المعدل")]


def _year_label(y) -> str:
    return f"{y}/{int(y) + 1}" if y not in (None, "") else ""


def build_workbook(report: dict, filters_text: str) -> bytes:
    """The report as an Excel file: a summary sheet, the group table and the students list (right to left)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    bold = Font(bold=True)
    head = PatternFill("solid", fgColor="DDE7F3")
    wb = Workbook()

    ws = wb.active
    ws.title = "الملخص"
    ws.sheet_view.rightToLeft = True
    s = report.get("summary") or {}
    rows = [("تقرير الطلاب", datetime.now().strftime("%Y-%m-%d %H:%M")), ("المرشحات", filters_text or "الكل"),
            ("إجمالي الطلاب", s.get("total", 0)), ("المتخرجون", s.get("graduated", 0)),
            ("غير المتخرجين", s.get("total", 0) - s.get("graduated", 0)),
            ("الذكور", s.get("male", 0)), ("الإناث", s.get("female", 0)), ("متوسط المعدل", s.get("avg_average"))]
    for r in rows:
        ws.append(list(r))
        ws.cell(ws.max_row, 1).font = bold
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 40

    keys = report.get("group_keys") or []
    if keys:
        wg = wb.create_sheet("التجميع")
        wg.sheet_view.rightToLeft = True
        wg.append([GROUP_OPTIONS.get(k, k) for k in keys] + [t for _, t in NUMBER_COLS])
        for g in report.get("groups") or []:
            wg.append([g.get(k) for k in keys] + [g.get(c) for c, _ in NUMBER_COLS])
        for c in wg[1]:
            c.font, c.fill = bold, head
        for i in range(1, len(keys) + len(NUMBER_COLS) + 1):
            wg.column_dimensions[wg.cell(1, i).column_letter].width = 26 if i <= len(keys) else 14

    wl = wb.create_sheet("الطلاب")
    wl.sheet_view.rightToLeft = True
    wl.append(["ت"] + [t for _, t in STUDENT_COLS])
    for i, st in enumerate(report.get("students") or [], start=1):
        wl.append([i] + [_year_label(st.get(c)) if c == "graduation_year" else st.get(c) for c, _ in STUDENT_COLS])
    for c in wl[1]:
        c.font, c.fill = bold, head
    wl.column_dimensions["B"].width = 36
    for col in "CDEFGHIJ":
        wl.column_dimensions[col].width = 16
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class ReportsScreen:
    def __init__(self):
        self.repo = ReportsRepository()
        self.report: dict | None = None
        try:
            self.departments = {d["id"]: d.get("name_ar") or "" for d in DepartmentRepository().get_all() or []}
        except Exception:
            self.departments = {}
        try:
            self.systems = {s["id"]: s.get("name_ar") or "" for s in StudySystemRepository().get_all() or []}
        except Exception:
            self.systems = {}
        this_year = datetime.now().year
        self.years = {y: f"{y}/{y + 1}" for y in range(this_year + 1, 2004, -1)}
        self.adm_years = {y: str(y) for y in range(this_year, 2000, -1)}
        self._build()

    # ── layout ───────────────────────────────────────────────────────────────
    def _build(self):
        with UI.page():
            with UI.card():
                UI.page_header("تقارير الطلاب", "أعداد الطلاب حسب المرشحات، مع جدول تجميع وتصدير إلى ملف إكسل",
                               actions=self._actions)
                with ui.grid(columns=4).classes("w-full gap-3"):
                    self.f_dept = UI.select("القسم", {0: "كل الأقسام", **self.departments}, value=0)
                    self.f_sys = UI.select("نظام الدراسة", {0: "كل الأنظمة", **self.systems}, value=0)
                    self.f_status = UI.select("حالة التخرج", {"": "الكل", "graduated": "متخرج",
                                                              "not_graduated": "غير متخرج"}, value="")
                    self.f_year = UI.select("سنة التخرج (أو المتوقعة)", {0: "كل السنوات", **self.years}, value=0)
                    self.f_sem = UI.select("الفصل", {"": "الكل", "first": "الأول", "second": "الثاني",
                                                     "summer": "الصيفي"}, value="")
                    self.f_adm = UI.select("سنة القبول", {0: "كل السنوات", **self.adm_years}, value=0)
                    self.f_gender = UI.select("الجنس", {0: "الكل", 1: "ذكر", 2: "أنثى"}, value=0)
                    self.f_nat = UI.select("الجنسية", {"": "الكل", "iraqi": "عراقي", "other": "غير عراقي"}, value="")
                    self.f_name = UI.input(label="الاسم يحتوي على")
                    self.f_group = UI.select("التجميع حسب", GROUP_OPTIONS, value="department")
                    self.f_then = UI.select("ثم حسب", {"": "بدون", **GROUP_OPTIONS}, value="")
                    with ui.row().classes("items-end"):
                        UI.primary_button("عرض التقرير", icon="query_stats", on_click=self._run)
            self.result = ui.column().classes("w-full gap-4")
        self._run()

    def _actions(self):
        UI.secondary_button("تصدير إلى إكسل", icon="download", on_click=self._export)

    def _filters(self) -> dict:
        return {"department_id": self.f_dept.value, "study_system_id": self.f_sys.value,
                "status": self.f_status.value, "graduation_year": self.f_year.value, "semester": self.f_sem.value,
                "admission_year": self.f_adm.value, "gender": self.f_gender.value,
                "nationality": self.f_nat.value, "name": (self.f_name.value or "").strip()}

    def _filters_text(self) -> str:
        parts = []
        for sel, label in ((self.f_dept, "القسم"), (self.f_sys, "النظام"), (self.f_status, "الحالة"),
                           (self.f_year, "سنة التخرج"), (self.f_sem, "الفصل"), (self.f_adm, "سنة القبول"),
                           (self.f_gender, "الجنس"), (self.f_nat, "الجنسية")):
            if sel.value not in (None, "", 0):
                parts.append(f"{label}: {sel.options.get(sel.value, sel.value)}")
        if (self.f_name.value or "").strip():
            parts.append(f"الاسم: {self.f_name.value.strip()}")
        return "، ".join(parts)

    # ── data ─────────────────────────────────────────────────────────────────
    def _run(self):
        then_by = self.f_then.value if self.f_then.value != self.f_group.value else ""
        self.report = self.repo.students_report(self._filters(), self.f_group.value, then_by)
        self.result.clear()
        with self.result:
            if self.report is None:
                UI.empty_state("تعذر إعداد التقرير", "التقارير تحتاج الاتصال بالخادم. تحقق من الاتصال ثم أعد المحاولة.",
                               icon="cloud_off")
                return
            s = self.report["summary"]
            with ui.grid(columns=5).classes("w-full gap-3"):
                UI.stat_card("إجمالي الطلاب", s["total"], "people")
                UI.stat_card("المتخرجون", s["graduated"], "school")
                UI.stat_card("غير المتخرجين", s["total"] - s["graduated"], "hourglass_empty")
                UI.stat_card("ذكور / إناث", f"{s['male']} / {s['female']}", "wc")
                UI.stat_card("متوسط المعدل", s["avg_average"] if s["avg_average"] is not None else "—", "grade")
            keys = self.report.get("group_keys") or []
            if keys:
                with UI.card():
                    UI.card_header("جدول التجميع", "table_chart")
                    cols = [{"name": k, "label": GROUP_OPTIONS[k], "field": k, "sortable": True} for k in keys]
                    cols += [{"name": c, "label": t, "field": c, "sortable": True} for c, t in NUMBER_COLS]
                    rows = [{"_k": i, **g} for i, g in enumerate(self.report["groups"])]
                    UI.data_table(cols, rows, row_key="_k")
            with UI.card():
                students = self.report.get("students") or []
                UI.card_header(f"قائمة الطلاب ({len(students)} من {s['total']})", "list")
                cols = [{"name": c, "label": t, "field": c, "sortable": True} for c, t in STUDENT_COLS]
                rows = [{**st, "graduation_year": _year_label(st.get("graduation_year"))} for st in students]
                table = UI.data_table(cols, rows, row_key="id")
                table.props("virtual-scroll").style("max-height: 520px")

    def _export(self):
        if not self.report:
            ui.notify("اعرض التقرير أولاً", type="warning")
            return
        # The file carries every matching student, not only the rows shown on screen
        full = self.repo.students_report(self._filters(), self.f_group.value,
                                         self.f_then.value if self.f_then.value != self.f_group.value else "",
                                         list_limit=20000) or self.report
        from utils.file_delivery import deliver_file
        deliver_file(build_workbook(full, self._filters_text()),
                     f"تقرير_الطلاب_{datetime.now():%Y%m%d_%H%M}.xlsx", auto_open=True)
