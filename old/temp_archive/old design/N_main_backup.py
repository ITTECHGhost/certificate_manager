from nicegui import ui
from data.repositories import DashboardRepository

class DashboardScreen:
    def __init__(self):
        self.repo = DashboardRepository()
        self.counts = {"total_students": 0, "total_departments": 0, "total_courses": 0, "total_personnel": 0}
        
        self.refresh_data()
        self.build_ui()

    def refresh_data(self):
        """Fetches data from the repository (handles online/offline seamlessly)."""
        try:
            self.counts = self.repo.get_counts()
        except Exception as e:
            print(f"Failed to fetch data: {e}")

    def build_ui(self):
        """Constructs a native-feeling desktop layout with a fixed sidebar and scrollable main area."""
        
        # Reset default browser margins/paddings and set the global native app background
        ui.query('body').classes('bg-[#0f172a] text-slate-200 m-0 p-0 overflow-hidden font-sans select-none')

        # Main App Layout Container (Flex row taking full screen)
        with ui.row().classes('w-full h-screen flex-nowrap m-0 p-0 gap-0'):
            
            # --- 1. FIXED LEFT SIDEBAR ---
            with ui.column().classes('w-64 h-full bg-[#020617] border-r border-slate-800 p-4 justify-between shrink-0'):
                
                # Top Navigation Area
                with ui.column().classes('w-full gap-2'):
                    ui.label('Certificate Manager').classes('text-lg font-bold text-white mb-6 tracking-wide px-2')
                    
                    self._nav_item('Dashboard', 'space_dashboard', active=True)
                    self._nav_item('Students', 'people', active=False)
                    self._nav_item('Graduation Orders', 'school', active=False)
                    self._nav_item('Settings', 'settings', active=False)
                
                # Bottom User Profile Area
                with ui.row().classes('w-full items-center gap-3 p-3 bg-slate-800/40 rounded-xl border border-slate-800/60 cursor-pointer hover:bg-slate-800/80 transition-colors'):
                    ui.icon('account_circle', size='sm').classes('text-slate-400')
                    with ui.column().classes('gap-0'):
                        ui.label('Admin User').classes('text-sm font-semibold text-slate-200 leading-tight')
                        ui.label('Online').classes('text-xs text-emerald-500 font-medium leading-tight')

            # --- 2. SCROLLABLE MAIN CONTENT ---
            with ui.scroll_area().classes('flex-grow h-full bg-[#0f172a] p-8'):
                with ui.column().classes('w-full max-w-6xl mx-auto gap-8'):
                    
                    # Top Header
                    with ui.row().classes('w-full justify-between items-end'):
                        with ui.column().classes('gap-1'):
                            ui.label('Overview').classes('text-3xl font-semibold tracking-tight text-white')
                            ui.label('System metrics and recent actions').classes('text-sm text-slate-400')
                        
                        ui.button('Refresh Data', icon='sync', on_click=self.refresh_data).classes(
                            'bg-slate-800 text-slate-300 hover:bg-slate-700 outline-none shadow-none rounded-lg px-4 py-2 font-medium capitalize'
                        )

                    # Stat Cards (1x4 Grid)
                    with ui.grid(columns=4).classes('w-full gap-5'):
                        self._stat_card("Total Students", self.counts.get("total_students", 0), "people", "text-blue-400", "bg-blue-500/10 border-blue-500/20")
                        self._stat_card("Departments", self.counts.get("total_departments", 0), "domain", "text-emerald-400", "bg-emerald-500/10 border-emerald-500/20")
                        self._stat_card("Courses", self.counts.get("total_courses", 0), "menu_book", "text-amber-400", "bg-amber-500/10 border-amber-500/20")
                        self._stat_card("Personnel", self.counts.get("total_personnel", 0), "badge", "text-purple-400", "bg-purple-500/10 border-purple-500/20")

                    # Bottom Section: Quick Actions & Table Split
                    with ui.row().classes('w-full gap-6 items-stretch'):
                        
                        # Quick Actions Panel (Takes up 1/3 of the row)
                        with ui.column().classes('w-1/3 p-6 bg-[#1e293b] rounded-2xl border border-slate-800 gap-4 shadow-xl'):
                            ui.label('Quick Actions').classes('text-lg font-semibold text-white mb-2')
                            self._action_btn('Add New Student', 'person_add', 'bg-blue-600 hover:bg-blue-500')
                            self._action_btn('Issue Certificate', 'workspace_premium', 'bg-emerald-600 hover:bg-emerald-500')
                            self._action_btn('Generate Report', 'summarize', 'bg-slate-700 hover:bg-slate-600')

                        # Recent Activity Table (Takes up 2/3 of the row)
                        with ui.column().classes('flex-grow p-6 bg-[#1e293b] rounded-2xl border border-slate-800 shadow-xl'):
                            ui.label('Recent Enrollments').classes('text-lg font-semibold text-white mb-4')
                            
                            # Clean, native-looking grid
                            columns = [
                                {'name': 'name', 'label': 'Student Name', 'field': 'name', 'align': 'left'},
                                {'name': 'dept', 'label': 'Department', 'field': 'dept', 'align': 'left'},
                                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'right'},
                            ]
                            rows = [
                                {'name': 'Ali Hassan', 'dept': 'Computer Science', 'status': 'Enrolled'},
                                {'name': 'Sara Ahmed', 'dept': 'Information Systems', 'status': 'Pending'},
                                {'name': 'Muna Youssef', 'dept': 'Network Security', 'status': 'Graduated'},
                            ]
                            
                            # The table styling is stripped back to match a desktop grid
                            ui.table(columns=columns, rows=rows, row_key='name').classes(
                                'w-full bg-transparent text-slate-300 no-shadow border-none'
                            ).props('flat bordered dark hide-bottom')


    def _nav_item(self, text: str, icon_name: str, active: bool = False):
        """Builds a sidebar navigation item."""
        bg_color = 'bg-blue-600/20 text-blue-400 border-blue-500/50' if active else 'bg-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border-transparent'
        with ui.row().classes(f'w-full items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all {bg_color}'):
            ui.icon(icon_name, size='sm')
            ui.label(text).classes('font-medium')

    def _stat_card(self, title: str, value: int, icon_name: str, icon_text_color: str, icon_bg_color: str):
        """Builds a metric card with a native UI aesthetic."""
        with ui.column().classes('p-5 bg-[#1e293b] rounded-2xl border border-slate-800 shadow-xl gap-4'):
            with ui.row().classes('w-full justify-between items-start'):
                with ui.element('div').classes(f'p-3 rounded-xl border {icon_bg_color} {icon_text_color}'):
                    ui.icon(icon_name, size='sm')
            with ui.column().classes('gap-1'):
                ui.label(str(value)).classes('text-3xl font-bold text-white')
                ui.label(title).classes('text-sm font-medium text-slate-400')

    def _action_btn(self, text: str, icon_name: str, colors: str):
        """Builds a full-width action button."""
        ui.button(text, icon=icon_name).classes(
            f'w-full {colors} text-white font-medium rounded-xl px-4 py-3 shadow-none outline-none normal-case justify-start'
        )

# Main Application Entry Point
if __name__ in {"__main__", "__mp_main__"}:
    DashboardScreen()
    # Launching as a dedicated Windows App using PyWebView
    ui.run(
        native=True, 
        port=8081,
        window_size=(1280, 800), 
        title="Certificate Manager", 
        reload=False,     # Disable reload for production
        dark=True         # Force dark mode to match our specific hex colors
    )
