import logging
import os
from nicegui import ui
from nicegui_ui.ui_components import UI
from data.repositories import StudentRepository, CertificateRepository, PersonnelRepository, OfflineModeError
from nicegui_screens.graduation_orders_screen import extract_event_value
import difflib

log = logging.getLogger(__name__)

class CertificateScreen:
    """
    Certificate Generation Screen (NiceGUI version).
    Uses full page view with split layout (Student info / Certificate options).
    """

    def __init__(self):
        self.student_repo = StudentRepository()
        self.cert_repo = CertificateRepository()
        self.personnel_repo = PersonnelRepository()
        
        self.selected_student = None
        self.student_full_data = None
        
        self.templates_dir = "templets"
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            
        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.build_ui()

    def get_templates(self) -> list[str]:
        try:
            files = [f for f in os.listdir(self.templates_dir) if f.endswith('.docx') and not f.startswith('~')]
            return files if files else ["لا توجد قوالب / No templates found"]
        except Exception:
            return ["لا توجد قوالب / No templates found"]

    def build_ui(self):
        self.container.clear()
        with self.container:
            # Header Bar
            with UI.card().classes("w-full p-4 shrink-0"):
                with ui.row().classes("w-full justify-between items-center"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("school", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إصدار الوثيقة — Issue Certificate").classes("text-xl font-bold app-text-primary")
                            ui.label("إنشاء وطباعة وثائق التخرج للطلاب").classes("text-xs app-text-muted")
                            
                    with ui.row().classes("items-center gap-2 flex-1 max-w-xl mx-4 relative"):
                        def on_search(e):
                            val = extract_event_value(e, default="")
                            self.search_term = str(val or "").strip()
                            self.perform_search()

                        self.search_input = UI.text_input(
                            label="",
                            placeholder="ابحث باسم الطالب (عربي/إنكليزي)...",
                            on_change=on_search
                        ).classes("flex-1 text-sm")
                        
                        UI.secondary_button("بحث", icon="search", on_click=self.perform_search).classes("px-4")

            # Main Content Split
            with ui.row().classes("w-full flex-1 gap-6 min-h-0 flex-nowrap"):
                
                # Left Panel: Student Info & Preview
                with UI.card().classes("flex-1 p-5 gap-4 overflow-y-auto border border-[var(--border-default)]"):
                    ui.label("معلومات الطالب — Student Info").classes("text-base font-bold app-text-accent mb-2")
                    
                    self.student_info_container = ui.column().classes("w-full gap-3")
                    self.render_empty_student_info()
                    
                    ui.label("معاينة السجل الأكاديمي — Academic Preview").classes("text-sm font-bold app-text-primary mt-4")
                    self.preview_text = ui.textarea().classes("w-full h-48 font-mono text-xs bg-[var(--bg-main)]").props("readonly")
                
                # Right Panel: Certificate Options
                with UI.card().classes("w-80 p-5 gap-4 overflow-y-auto shrink-0 border border-[var(--border-default)] bg-[var(--bg-card)]"):
                    ui.label("خيارات الوثيقة — Options").classes("text-base font-bold app-text-accent mb-2")
                    
                    self.template_sel = UI.select(
                        "قالب الوثيقة / Template",
                        options={t: t for t in self.get_templates()},
                        value=self.get_templates()[0] if self.get_templates() else None
                    ).classes("w-full text-sm")
                    
                    self.to_input = UI.text_input("إلى / To", placeholder="جهة الإصدار").classes("w-full text-sm")
                    
                    # Order Info
                    self.chk_order = ui.checkbox("الأمر الجامعي / University Order", value=False)
                    with ui.row().classes("w-full gap-2 pl-6"):
                        self.order_num = UI.text_input("الرقم", placeholder="").classes("flex-1 text-xs")
                        self.order_date = UI.text_input("التاريخ", placeholder="YYYY-MM-DD").classes("flex-1 text-xs")

                    # Rank Info
                    self.chk_rank = ui.checkbox("تسلسل التخرج / Graduation Rank", value=False)
                    with ui.row().classes("w-full gap-2 pl-6"):
                        self.rank_val = UI.text_input("الترتيب", placeholder="").classes("w-16 text-xs")
                        self.rank_total = UI.text_input("العدد", placeholder="").classes("w-16 text-xs")
                        self.rank_avg = UI.text_input("معدل الاول", placeholder="").classes("flex-1 text-xs")

                    ui.separator().classes("my-2")
                    
                    # Actions
                    self.btn_generate = UI.success_button(
                        "📄 إصدار الوثيقة (Word)",
                        icon="download",
                        on_click=self.generate_certificate
                    ).classes("w-full py-3 mt-4")
                    self.btn_generate.disable()

        # Search Results Dialog
        self.search_dialog = ui.dialog()
        with self.search_dialog, UI.card().classes("w-[600px] max-w-full p-0 overflow-hidden"):
            with ui.row().classes("w-full justify-between items-center p-4 bg-[var(--bg-panel)] border-b border-[var(--border-default)]"):
                ui.label("نتائج البحث — Search Results").classes("text-lg font-bold")
                ui.button(icon="close", on_click=self.search_dialog.close).props("flat round dense")
            self.search_results_container = ui.column().classes("w-full max-h-[400px] overflow-y-auto p-4 gap-2")

    def perform_search(self):
        if not hasattr(self, 'search_term') or len(self.search_term) < 2:
            return
            
        try:
            results = self.student_repo.search(self.search_term, limit=15)
            if not results:
                ui.notify("لم يتم العثور على طالب / No student found", type="warning")
                return
                
            self.search_results_container.clear()
            with self.search_results_container:
                for row in results:
                    dept = row.get("dept_name_ar", "")
                    year = str(row.get("graduation_year") or row.get("admission_year", ""))
                    
                    with ui.row().classes("w-full justify-between items-center p-3 rounded-lg hover:bg-[var(--bg-hover)] cursor-pointer border border-[var(--border-default)] transition-colors").on('click', lambda r=row: self.select_student(r)):
                        with ui.column().classes("gap-0"):
                            ui.label(row.get("full_name_ar", "")).classes("font-bold text-sm")
                            ui.label(row.get("full_name_en", "")).classes("text-xs text-gray-500 font-mono")
                        with ui.column().classes("items-end gap-0"):
                            ui.label(dept).classes("text-xs font-bold text-blue-500")
                            ui.label(f"دفعة {year}").classes("text-[10px] text-gray-400")
            
            self.search_dialog.open()
        except Exception as e:
            ui.notify(f"Search failed: {e}", type="negative")

    def render_empty_student_info(self):
        self.student_info_container.clear()
        with self.student_info_container:
            ui.label("الرجاء البحث واختيار طالب لعرض معلوماته.").classes("text-sm text-gray-400 mt-8 text-center w-full")

    def select_student(self, student_row):
        self.search_dialog.close()
        self.selected_student = student_row
        student_id = student_row["id"]
        
        try:
            # Requires CertificateRepository.get_full_certificate_data to exist in repositories.py
            self.student_full_data = self.cert_repo.get_full_certificate_data(student_id)
            if not self.student_full_data:
                ui.notify("لا توجد بيانات دراسية / No academic data", type="warning")
                return
                
            self.update_student_ui()
            self.btn_generate.enable()
        except Exception as e:
            ui.notify(f"Error loading student: {e}", type="negative")
            log.error(f"Failed to load certificate data: {e}")

    def update_student_ui(self):
        data = self.student_full_data
        self.student_info_container.clear()
        
        avg = data.get("average")
        rank_text = f"{data.get('rank', '—')} of {data.get('total_graduates', '—')}"
        
        with self.student_info_container:
            with ui.row().classes("w-full gap-4"):
                with UI.card().classes("flex-1 p-3 bg-[var(--bg-main)]"):
                    ui.label("الاسم / Name").classes("text-[10px] text-gray-500")
                    ui.label(data.get("full_name_en", "")).classes("font-bold text-sm")
                with UI.card().classes("flex-1 p-3 bg-[var(--bg-main)]"):
                    ui.label("القسم / Dept").classes("text-[10px] text-gray-500")
                    ui.label(data.get("dept_name_en", "")).classes("font-bold text-sm")
                    
            with ui.row().classes("w-full gap-4"):
                with UI.card().classes("flex-1 p-3 bg-[var(--bg-main)]"):
                    ui.label("المعدل / Average").classes("text-[10px] text-gray-500")
                    ui.label(str(avg) if avg else "—").classes("font-bold text-sm text-green-500")
                with UI.card().classes("flex-1 p-3 bg-[var(--bg-main)]"):
                    ui.label("الترتيب / Rank").classes("text-[10px] text-gray-500")
                    ui.label(rank_text).classes("font-bold text-sm text-blue-500")

        # Auto-fill options
        order_num = data.get("order_number")
        if order_num:
            self.chk_order.value = True
            self.order_num.value = str(order_num)
            if data.get("order_date"):
                self.order_date.value = str(data.get("order_date"))
        else:
            self.chk_order.value = False
            self.order_num.value = ""
            self.order_date.value = ""
            
        rank_val = data.get("rank")
        if rank_val:
            self.chk_rank.value = True
            self.rank_val.value = str(rank_val)
            self.rank_total.value = str(data.get("total_graduates") or "")
            self.rank_avg.value = str(round(float(data.get("top_average", 0)), 3) if data.get("top_average") else "")
        else:
            self.chk_rank.value = False
            
        # Update preview
        preview_lines = ["--- LIVE PREVIEW ---", ""]
        for period in data.get("periods", []):
            preview_lines.append(f"[{period.get('academic_year', '')} - Stage {period.get('stage_number', '')}]")
            for enr in period.get("enrollments", []):
                cname = enr.get('course_name_en', '')
                preview_lines.append(f"  • {cname[:30]:<30} | Mark: {enr.get('score', '')}")
            preview_lines.append("")
            
        self.preview_text.value = "\n".join(preview_lines)

    def generate_certificate(self):
        ui.notify("وظيفة إنشاء Word سيتم دعمها لاحقاً / Word generation pending backend API port.", type="info")
        # In a real NiceGUI deployment, we'd use docxtpl here, save to temp file, and use ui.download(temp_path).
