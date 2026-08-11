import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

log = logging.getLogger(__name__)

class StudentProfileView:
    def __init__(self, repo, parent_container, on_back):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        
    def render(self, student_row):
        """Render the profile view inside the parent container"""
        student_id = student_row.get("id")
        if not student_id:
            ui.notify("Error: No student ID provided", type="negative")
            return
            
        data = self.repo.get_by_id(student_id)
        if not data:
            ui.notify(f"Could not load data for student ID: {student_id}", type="negative")
            return
            
        self.parent.clear()
        with self.parent:
            with UI.card().classes('flex-1'):
                # Header
                with ui.row().classes('w-full justify-between items-center pb-3 app-card-header'):
                    with ui.row().classes('items-center gap-4'):
                        ui.button(icon='arrow_back', on_click=self.on_back).props('flat round dense').classes('app-text-primary')
                        ui.icon('person', size='sm').classes('app-text-accent')
                        with ui.column().classes('gap-0'):
                            ui.label(data.get("full_name_ar") or data.get("full_name_en") or "Unknown").classes('text-xl font-bold app-text-primary')
                            ui.label(f"{data.get('dept_name_ar', 'Unknown Dept')} • {data.get('graduation_year', 'N/A')}").classes('text-sm app-text-muted')
                    
                    UI.primary_button('Edit Student', icon='edit', on_click=lambda: ui.notify("Edit clicked (WIP)"))
                    
                # Tabs
                with ui.tabs().classes('w-full border-b border-[var(--border-default)] app-text-primary shrink-0') as tabs:
                    info_tab = ui.tab('Info')
                    academic_tab = ui.tab('Academic')
                    periods_tab = ui.tab('Periods & Grades')
                    
                with ui.tab_panels(tabs, value=info_tab).classes('w-full flex-1 overflow-y-auto mt-4 bg-transparent'):
                    with ui.tab_panel(info_tab):
                        with ui.row().classes('w-full gap-12'):
                            with ui.column().classes('gap-4 app-text-primary'):
                                ui.label("Personal Details").classes('font-bold text-lg mb-2 app-text-accent')
                                
                                gender_map = {1: "ذكر / Male", 2: "أنثى / Female"}
                                gender_val = data.get("gender")
                                gender_str = gender_map.get(gender_val, gender_val) if gender_val else "—"
                                
                                ui.label(f"Gender: {gender_str}")
                                ui.label(f"Date of Birth: {data.get('date_of_birth', '—')}")
                                ui.label(f"Nationality: {data.get('nationality_ar', '—')}")
                                ui.label(f"Birthplace: {data.get('birthplace_ar') or data.get('birthplace_other') or '—'}")
                    
                    with ui.tab_panel(academic_tab):
                        with ui.row().classes('w-full gap-12'):
                            with ui.column().classes('gap-4 app-text-primary flex-1'):
                                ui.label("Academic Details").classes('font-bold text-lg mb-2 app-text-accent')
                                ui.label(f"Study System: {data.get('study_system_name_ar', '—')}")
                                ui.label(f"Study Type: {data.get('study_type', '—')}")
                                ui.label(f"Admission Year: {data.get('admission_year', '—')}")
                                ui.label(f"Average: {data.get('average', '—')}")
                            
                            with ui.column().classes('gap-4 app-text-primary flex-1'):
                                ui.label("Graduation Details").classes('font-bold text-lg mb-2 app-text-accent')
                                ui.label(f"Order: {data.get('order_number', '—')}")
                                ui.label(f"Graduation Date: {data.get('graduation_date', '—')}")
                                ui.label(f"Sequence: {data.get('sequence_number', '—')}")
                                ui.label(f"Semester/Role: {data.get('graduation_semester', '—')}")
                    
                    with ui.tab_panel(periods_tab):
                        with ui.row().classes('w-full justify-between items-center mb-4'):
                            ui.label("Academic Periods").classes('font-bold text-lg app-text-accent')
                            UI.success_button("Add Period", icon='add', on_click=lambda: ui.notify('Add Period WIP'))
                        
                        # Stub table for periods
                        columns = [
                            {"name": "year", "label": "Academic Year", "field": "year", "align": "left"},
                            {"name": "stage", "label": "Stage", "field": "stage", "align": "center"},
                            {"name": "status", "label": "Status", "field": "status", "align": "center"},
                            {"name": "actions", "label": "Actions", "field": "actions", "align": "right"},
                        ]
                        ui.table(columns=columns, rows=[], row_key='id').classes(Styles.TABLE_CLASSES).props('flat bordered')


class StudentFormView:
    def __init__(self, repo, parent_container, on_back, on_save_callback=None):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        self.on_save = on_save_callback
        
    def render_add(self):
        """Render form in add mode"""
        self._build_ui(mode="Add New Student")
        
    def render_edit(self, student_row):
        """Render form in edit mode"""
        self._build_ui(mode="Edit Student", data=student_row)
        
    def _build_ui(self, mode="Add New Student", data=None):
        self.parent.clear()
        with self.parent:
            with UI.card().classes('flex-1'):
                # Header
                with ui.row().classes('w-full justify-between items-center pb-3 app-card-header'):
                    with ui.row().classes('items-center gap-3'):
                        ui.button(icon='arrow_back', on_click=self.on_back).props('flat round dense').classes('app-text-primary')
                        UI.section_header(mode)
                    ui.icon('person_add' if mode == 'Add New Student' else 'edit', size='sm').classes('app-text-accent')
                    
                # Form Body
                with ui.column().classes('w-full flex-1 overflow-y-auto gap-8 mt-4'):
                    
                    # Section: Name
                    ui.label("Name / الاسم").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.name_ar = UI.text_input("Full Arabic Name / الاسم الكامل بالعربية").classes('flex-1')
                        self.name_en = UI.text_input("Full English Name / الاسم الكامل بالإنكليزية").classes('flex-1')
                    
                    # Section: Personal
                    ui.label("Personal Details / البيانات الشخصية").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.dob = UI.text_input("Date of Birth (YYYY-MM-DD)").classes('flex-1')
                        self.nationality = UI.select("Nationality", {"IQ": "Iraq", "OTHER": "Other"}).classes('flex-1')
                        self.gender = UI.select("Gender", {1: "Male", 2: "Female"}).classes('flex-1')
                    
                    # Section: Academic
                    ui.label("Academic / الدراسة").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.department = UI.select("Department", {"—": "—"}).classes('flex-1')
                        self.degree = UI.select("Degree Level", {1: "Bachelor", 2: "Higher Diploma", 3: "Master", 4: "PhD"}, value=1).classes('flex-1')
                        self.study_system = UI.select("Study System", {1: "Annual / صباحي", 2: "Semester / مسائي"}).classes('flex-1')
                    
                    # Section: Thesis (Dynamic)
                    self.thesis_container = ui.column().classes('w-full gap-4 hidden')
                    ui.label("Thesis / الرسالة").classes('text-lg font-bold app-text-accent w-full').move(self.thesis_container)
                    with ui.row().classes('w-full gap-4').move(self.thesis_container):
                        self.thesis_ar = UI.text_input("Thesis Title (AR)").classes('flex-1')
                        self.thesis_en = UI.text_input("Thesis Title (EN)").classes('flex-1')
                    
                    # Toggle thesis visibility based on degree
                    def on_degree_change(e):
                        if e.value in [2, 3, 4]:
                            self.thesis_container.classes(remove='hidden')
                        else:
                            self.thesis_container.classes(add='hidden')
                    self.degree.on_value_change(on_degree_change)
                    
                    # Section: Graduation
                    ui.label("Graduation / التخرج").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.grad_date = UI.text_input("Graduation Date").classes('flex-1')
                        self.average = UI.text_input("Average (50-100)").classes('flex-1')
                        self.sequence = UI.text_input("Sequence Number").classes('flex-1')
                    
                # Footer
                with ui.row().classes('w-full pt-4 mt-4 justify-end gap-4 shrink-0 app-card-header'):
                    UI.success_button('Save / حفظ', icon='save', on_click=self.save)
                    UI.secondary_button('Cancel / إلغاء', on_click=self.on_back)

            # Populate data if edit
            if data:
                self.name_ar.value = data.get("full_name_ar", "")
                self.name_en.value = data.get("full_name_en", "")
                self.dob.value = data.get("date_of_birth", "")
                self.gender.value = data.get("gender")
                self.degree.value = data.get("degree_level")
                on_degree_change(type('Event', (), {'value': self.degree.value})())
                
    def save(self):
        ui.notify("Save functionality not yet connected to database in this mockup.", type="warning")
        if self.on_save:
            self.on_save()
        self.on_back()
