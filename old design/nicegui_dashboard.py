from nicegui import ui

# --- Theme & Color Mappings ---
theme_colors = {
    'light': {
        'workspace_bg': 'bg-gray-100',
        'sidebar_bg': 'bg-white',
        'bottom_bg': 'bg-[#1A1C23]',
        'card_bg': 'bg-white',
        'text_main': 'text-gray-900',
        'text_muted': 'text-gray-500',
        'border_color': 'border-gray-200',
        'divider': 'bg-gray-200'
    },
    'dark': {
        'workspace_bg': 'bg-[#15171E]',
        'sidebar_bg': 'bg-[#1B1E27]',
        'bottom_bg': 'bg-[#0F1115]',
        'card_bg': 'bg-[#222631]',
        'text_main': 'text-slate-100',
        'text_muted': 'text-gray-400',
        'border_color': 'border-gray-850',
        'divider': 'bg-gray-800'
    }
}

accent_colors = {
    'blue': {
        'hex': '#3B82F6',
        'rgb': '59, 130, 246',
        'text': 'text-blue-500'
    },
    'purple': {
        'hex': '#A855F7',
        'rgb': '168, 85, 247',
        'text': 'text-purple-500'
    },
    'emerald': {
        'hex': '#10B981',
        'rgb': '16, 185, 129',
        'text': 'text-emerald-500'
    }
}

class DashboardState:
    def __init__(self):
        self.theme = 'light'
        self.accent = 'purple'

    def set_theme(self, theme):
        self.theme = theme
        if theme == 'dark':
            ui.dark_mode().enable()
        else:
            ui.dark_mode().disable()
        render_dashboard.refresh()

    def set_accent(self, accent):
        self.accent = accent
        render_dashboard.refresh()

state = DashboardState()

# Disable nicegui default body margins & padding
ui.query('.q-page').classes('p-0')
ui.query('body').classes('bg-[#0E1117] overflow-x-hidden')

@ui.refreshable
def render_dashboard():
    tc = theme_colors[state.theme]
    ac = accent_colors[state.accent]
    rgba_bg = f"rgba({ac['rgb']}, 0.1)" if state.theme == 'light' else f"rgba({ac['rgb']}, 0.15)"
    
    # Outer layout container matching the dark window color scheme
    with ui.column().classes('w-full min-h-screen bg-[#0E1117] items-center justify-between p-6 gap-6'):
        
        # 1. Top Header
        with ui.row().classes('w-full max-w-5xl justify-between items-center px-2'):
            ui.label('Certificate Management Dashboard').classes('text-white text-xl font-bold font-sans')
            
        # 2. Main Content Card (Left Dashboard Panel + Right Sidebar)
        with ui.row().classes(f'w-full max-w-5xl rounded-2xl overflow-hidden shadow-2xl flex-nowrap gap-0 border {tc["border_color"]}'):
            
            # Left Dashboard Workspace (75% width)
            with ui.column().classes(f'w-3/4 {tc["workspace_bg"]} p-8 gap-6'):
                # Title & Subtitle
                with ui.column().classes('gap-1'):
                    ui.label('Dashboard').classes(f'text-2xl font-bold {tc["text_main"]} font-sans')
                    ui.label('Welcome back to the Certificate Management System').classes(f'{tc["text_muted"]} text-sm')
                
                # KPI Grid (2x2 layout)
                with ui.grid(columns=2).classes('w-full gap-6 mt-4'):
                    kpis = [
                        ('STUDENTS', '1618', '👤'),
                        ('DEPARTMENTS', '2', '🏢'),
                        ('COURSES', '185', '📚'),
                        ('PERSONNEL', '13', '👔')
                    ]
                    for title, val, emoji in kpis:
                        with ui.row().classes(f'{tc["card_bg"]} p-5 rounded-xl items-center shadow-md border {tc["border_color"]} w-full gap-4'):
                            # Emoji Icon Container
                            with ui.element('div').classes('w-12 h-12 rounded-lg flex items-center justify-center') \
                                .style(f'background-color: {rgba_bg};'):
                                ui.label(emoji).classes('text-2xl')
                            
                            # Info Column
                            with ui.column().classes('gap-0'):
                                ui.label(title).classes(f'{tc["text_muted"]} text-xs font-bold tracking-wider font-sans')
                                ui.label(val).classes(f'{tc["text_main"]} text-2xl font-extrabold font-sans')

                # Quick Actions
                with ui.column().classes('w-full gap-3 mt-4'):
                    ui.label('Quick Actions').classes(f'text-lg font-bold {tc["text_main"]} font-sans')
                    with ui.row().classes('gap-3'):
                        for action in ['Add New Student', 'Issue Certificate', 'Add New Course']:
                            ui.button(action, on_click=lambda a=action: ui.notify(f'Clicked: {a}')) \
                                .style(f'background-color: {ac["hex"]}; text-transform: none; font-weight: bold; border-radius: 8px;') \
                                .classes('text-white px-5 py-2 text-sm shadow-md hover:brightness-95')

                # Recent Activity
                with ui.column().classes('w-full gap-3 mt-4'):
                    with ui.column().classes(f'w-full {tc["card_bg"]} rounded-xl shadow-md border {tc["border_color"]} p-5 gap-3'):
                        ui.label('Recent Activity').classes(f'text-base font-bold {tc["text_main"]} mb-2 font-sans')
                        
                        activities = [
                            ('John Doe', 'Issued', '2 mins ago'),
                            ('Jane Smith', 'Pending', '1 hour ago'),
                            ('Global HR', 'Updated', '3 hours ago')
                        ]
                        
                        for i, (name, status, time_str) in enumerate(activities):
                            if i > 0:
                                ui.separator().classes(f'{tc["divider"]} my-1')
                            with ui.row().classes('w-full justify-between items-center py-1'):
                                ui.label(name).classes(f'{tc["text_main"]} font-medium text-sm font-sans w-1/3')
                                ui.label(status).classes(f'{ac["text"]} font-bold text-sm font-sans text-center w-1/3')
                                ui.label(time_str).classes(f'{tc["text_muted"]} text-xs text-right w-1/3 font-sans')

            # Right Sidebar (25% width)
            with ui.column().classes(f'w-1/4 {tc["sidebar_bg"]} p-8 gap-6'):
                ui.label('Management').classes(f'text-lg font-bold {tc["text_main"]} font-sans')
                
                nav_items = ['Home', 'Students', 'Departments', 'Courses', 'Personnel', 'Change Log']
                with ui.column().classes('w-full gap-2'):
                    for item in nav_items:
                        if item == 'Home':
                            # Active navigation item (Home) with dynamic transparent bg
                            with ui.row().classes('w-full rounded-lg px-4 py-2 items-center') \
                                .style(f'background-color: {rgba_bg};'):
                                ui.label(item).classes(f'{ac["text"]} font-bold text-sm font-sans')
                        else:
                            # Inactive navigation items
                            with ui.row().classes(f'w-full rounded-lg px-4 py-2 items-center cursor-pointer hover:{tc["workspace_bg"]}'):
                                ui.label(item).classes(f'{tc["text_muted"]} font-medium text-sm font-sans hover:{tc["text_main"]}')

        # 3. Bottom Controls Panel
        with ui.column().classes(f'w-full max-w-5xl {tc["bottom_bg"]} rounded-xl p-6 gap-4 shadow-lg border {tc["border_color"]}'):
            # Stats Summary Row
            with ui.row().classes('w-full justify-around items-center text-center'):
                stats = [
                    ('Students', '1618'),
                    ('Departments', '2'),
                    ('Courses', '185'),
                    ('Personnel', '13')
                ]
                for label, value in stats:
                    with ui.column().classes('gap-0'):
                        ui.label(label).classes('text-gray-400 text-xs font-sans')
                        ui.label(value).classes('text-white text-sm font-bold font-sans')

            ui.separator().classes('bg-gray-800/80')

            # Toggles Row
            with ui.row().classes('w-full justify-between items-center px-4'):
                # Theme selector
                with ui.row().classes('items-center gap-3'):
                    ui.label('Theme').classes('text-white text-xs font-bold font-sans')
                    with ui.row().classes('bg-[#0E1117] p-1 rounded-lg gap-1 border border-gray-800'):
                        for t in ['light', 'dark']:
                            is_active = (state.theme == t)
                            if is_active:
                                active_class = 'bg-[#1F2937] text-white border border-white'
                            else:
                                active_class = 'bg-transparent text-gray-400 hover:text-white'
                            ui.button(t, on_click=lambda t_val=t: state.set_theme(t_val)) \
                                .classes(f'{active_class} px-4 py-1 text-xs font-bold lowercase rounded-md min-h-0 h-7') \
                                .props('unelevated')

                # Accent Hue selector
                with ui.row().classes('items-center gap-3'):
                    ui.label('Accent Hue').classes('text-white text-xs font-bold font-sans')
                    with ui.row().classes('bg-[#0E1117] p-1 rounded-lg gap-1 border border-gray-800'):
                        for color in ['blue', 'purple', 'emerald']:
                            is_active = (state.accent == color)
                            if is_active:
                                active_class = 'bg-[#1F2937] text-white border border-white'
                            else:
                                active_class = 'bg-transparent text-gray-400 hover:text-white'
                            ui.button(color, on_click=lambda c_val=color: state.set_accent(c_val)) \
                                .classes(f'{active_class} px-4 py-1 text-xs font-bold lowercase rounded-md min-h-0 h-7') \
                                .props('unelevated')

# First render execution
render_dashboard()

# Dynamically fall back to browser-based mode if pywebview is not installed
try:
    import webview
    has_webview = True
except ImportError:
    has_webview = False

if has_webview:
    ui.run(native=True, window_size=(1024, 768), title="Certificate Management Dashboard", port=8060)
else:
    print("Native mode not supported because 'pywebview' is not installed. Falling back to browser-based mode on port 8060.")
    ui.run(title="Certificate Management Dashboard", port=8060)