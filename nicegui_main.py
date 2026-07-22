import os
import sys
import logging
from typing import Any
import requests

from nicegui import ui, run

# Re-use standard database logic and sync engines from the original application
from db import get_connection, init_db
from sync_engine import (
    init_local_db, check_network_status, set_online, is_online,
    sync_offline_queue_to_mysql, get_queue_status,
    pull_mysql_to_sqlite_background, download_mysql_snapshot,
    get_local_connection,
)
from config import (
    NAV_ITEMS, SETTINGS_ITEM, SCREEN_HEADERS,
    refresh_config
)
from data.repositories import (
    StudentRepository, DepartmentRepository, CourseRepository,
    PersonnelRepository, GraduationOrderRepository, CertificateRepository,
    AuditRepository, SettingsRepository, DashboardRepository
)

# ---------------------------------------------------------------------------
# Global Logging Setup (Text Files)
# ---------------------------------------------------------------------------
logging.getLogger().handlers.clear()

system_logger = logging.getLogger("system")
system_logger.setLevel(logging.INFO)
system_logger.handlers.clear()
system_logger.propagate = False

sys_handler = logging.FileHandler("system_log.txt", mode="a", encoding="utf-8")
sys_handler.setFormatter(logging.Formatter('%(asctime)s [SYSTEM] %(levelname)s: %(message)s'))
system_logger.addHandler(sys_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(message)s'))
system_logger.addHandler(stream_handler)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(sys_handler)
root_logger.addHandler(stream_handler)

activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
activity_logger.handlers.clear()
activity_logger.propagate = False

act_handler = logging.FileHandler("activity_log.txt", mode="a", encoding="utf-8")
act_handler.setFormatter(logging.Formatter('%(asctime)s [ACTIVITY] %(message)s'))
activity_logger.addHandler(act_handler)

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

logger.info("NiceGUI Application starting...")

# Initialize databases
try:
    init_db()
except Exception as _init_err:
    system_logger.warning("MySQL unavailable at startup: %s — starting in offline mode.", _init_err)
    set_online(False)
init_local_db()

# --- Design Custom System Tokens ---
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

class AppState:
    def __init__(self):
        self.current_user = None
        self.active_page = 'home'
        self.theme = 'light'
        self.accent = 'purple'
        self.search_query = ''
        self.online = True

    def login(self, user_data):
        self.current_user = user_data
        self.active_page = 'home'
        activity_logger.info(f"User {user_data.get('username')} logged in.")
        render_app.refresh()

    def logout(self):
        username = self.current_user.get('username') if self.current_user else 'Unknown'
        self.current_user = None
        self.active_page = 'home'
        activity_logger.info(f"User {username} logged out.")
        render_app.refresh()

    def set_page(self, page):
        self.active_page = page
        self.search_query = ''
        render_workspace.refresh()
        render_sidebar.refresh()

    def set_search(self, q):
        self.search_query = q or ''
        render_workspace.refresh()

    def set_theme(self, theme):
        self.theme = theme
        if theme == 'dark':
            ui.dark_mode().enable()
        else:
            ui.dark_mode().disable()
        render_app.refresh()

    def set_accent(self, accent):
        self.accent = accent
        render_app.refresh()

    def set_online(self, online_val):
        if self.online != online_val:
            self.online = online_val
            set_online(online_val)
            render_header.refresh()

state = AppState()

# Disable nicegui default body padding & margins
ui.query('.q-page').classes('p-0')
ui.query('body').classes('bg-[#0E1117] overflow-x-hidden')

# --- Login Action ---
def attempt_login(username_val, password_val, error_label):
    username = (username_val or '').strip()
    password = (password_val or '').strip()

    if not username or not password:
        error_label.set_text("يرجى إدخال اسم المستخدم وكلمة المرور")
        return

    # Fallback for offline/testing check
    if username == "1" and password == "1":
        user_data = {"id": 1, "username": "1", "role": "admin", "name_ar": "مدير النظام (مؤقت)"}
        state.login(user_data)
        return

    try:
        repo = PersonnelRepository()
        user_data = repo.authenticate(username, password)
        if user_data:
            state.login(user_data)
        else:
            error_label.set_text("اسم المستخدم أو كلمة المرور غير صحيحة")
    except Exception as e:
        error_label.set_text(f"خطأ في الاتصال: {e}")

# --- Login Screen UI ---
def render_login_screen():
    with ui.column().classes('w-full min-h-screen bg-[#0E1117] items-center justify-center p-4'):
        with ui.card().classes('w-96 p-8 rounded-2xl shadow-2xl bg-white dark:bg-[#222631] items-center gap-5'):
            
            # Application Logo
            try:
                ui.image('csit.png').classes('w-32 h-32')
            except Exception:
                ui.label('🎓').classes('text-6xl')

            ui.label('تسجيل الدخول / Login').classes('text-xl font-extrabold text-gray-800 dark:text-gray-100 font-sans')
            
            # Fields
            username_input = ui.input(placeholder='اسم المستخدم / Username').classes('w-full').props('outlined')
            password_input = ui.input(placeholder='كلمة المرور / Password').classes('w-full').props('outlined type=password password-toggle')
            
            error_lbl = ui.label('').classes('text-red-500 text-xs text-center')
            
            # Log in trigger
            ui.button('دخول / Sign In', on_click=lambda: attempt_login(username_input.value, password_input.value, error_lbl)) \
                .style('background-color: #A855F7; text-transform: none; font-weight: bold; border-radius: 8px;') \
                .classes('w-full text-white py-2')
            
            # Setup keyboard Enter bindings
            username_input.on('keydown.enter', lambda: attempt_login(username_input.value, password_input.value, error_lbl))
            password_input.on('keydown.enter', lambda: attempt_login(username_input.value, password_input.value, error_lbl))

# --- Refreshable Layout Slots ---
@ui.refreshable
def render_header():
    tc = theme_colors[state.theme]
    ac = accent_colors[state.accent]
    
    with ui.row().classes('w-full justify-between items-center px-6 py-4 bg-[#111827] border-b border-gray-800'):
        # Bilingual Screen Header Title
        ar_title, en_title = SCREEN_HEADERS.get(state.active_page, (state.active_page, state.active_page))
        with ui.row().classes('items-center gap-4'):
            ui.label(ar_title).classes('text-white text-lg font-bold font-sans')
            ui.label('|').classes('text-gray-600')
            ui.label(en_title).classes('text-gray-400 text-sm font-sans')
            
        # Network & Profile details
        with ui.row().classes('items-center gap-6'):
            # Network indicator
            if state.online:
                ui.label('🟢 متصل (Online)').classes('text-green-500 text-xs font-sans')
            else:
                ui.label('🔴 وضع عدم الاتصال (Offline Mode)').classes('text-red-500 text-xs font-sans')
                
            # User profile Info
            if state.current_user:
                name = state.current_user.get('name_ar') or state.current_user.get('username') or "مستخدم"
                role = state.current_user.get('role', '')
                ui.label(f"👤 {name} - {role}").classes('text-gray-200 text-xs font-bold')
                
            # Logout
            ui.button('Logout', on_click=state.logout).props('flat dense').classes('text-red-400 text-xs hover:text-red-500')

@ui.refreshable
def render_sidebar():
    tc = theme_colors[state.theme]
    ac = accent_colors[state.accent]
    rgba_bg = f"rgba({ac['rgb']}, 0.1)" if state.theme == 'light' else f"rgba({ac['rgb']}, 0.15)"
    
    with ui.column().classes(f'w-1/4 {tc["sidebar_bg"]} p-8 gap-6 min-h-[500px]'):
        ui.label('الإدارة — Management').classes(f'text-lg font-bold {tc["text_main"]} font-sans border-b pb-2').classes(tc['border_color'])
        
        with ui.column().classes('w-full gap-2'):
            for item in NAV_ITEMS:
                is_active = (state.active_page == item['key'])
                if is_active:
                    with ui.row().classes('w-full rounded-lg px-4 py-2 items-center') \
                        .style(f'background-color: {rgba_bg};'):
                        ui.label(f"{item['icon']} {item['ar']}").classes(f'{ac["text"]} font-bold text-sm font-sans')
                else:
                    with ui.row().classes(f'w-full rounded-lg px-4 py-2 items-center cursor-pointer hover:{tc["workspace_bg"]}') \
                        .on('click', lambda k=item['key']: state.set_page(k)):
                        ui.label(f"{item['icon']} {item['ar']}").classes(f'{tc["text_muted"]} font-medium text-sm font-sans hover:{tc["text_main"]}')
                        
            # Settings Item
            is_active = (state.active_page == SETTINGS_ITEM['key'])
            if is_active:
                with ui.row().classes('w-full rounded-lg px-4 py-2 items-center mt-6') \
                    .style(f'background-color: {rgba_bg};'):
                    ui.label(f"{SETTINGS_ITEM['icon']} {SETTINGS_ITEM['ar']}").classes(f'{ac["text"]} font-bold text-sm font-sans')
            else:
                with ui.row().classes(f'w-full rounded-lg px-4 py-2 items-center cursor-pointer mt-6 hover:{tc["workspace_bg"]}') \
                    .on('click', lambda k=SETTINGS_ITEM['key']: state.set_page(k)):
                    ui.label(f"{SETTINGS_ITEM['icon']} {SETTINGS_ITEM['ar']}").classes(f'{tc["text_muted"]} font-medium text-sm font-sans hover:{tc["text_main"]}')

@ui.refreshable
def render_workspace():
    tc = theme_colors[state.theme]
    ac = accent_colors[state.accent]
    rgba_bg = f"rgba({ac['rgb']}, 0.1)" if state.theme == 'light' else f"rgba({ac['rgb']}, 0.15)"
    
    with ui.column().classes(f'w-3/4 {tc["workspace_bg"]} p-8 gap-6'):
        if state.active_page == 'home':
            render_home_screen(tc, ac, rgba_bg)
        elif state.active_page == 'settings':
            render_settings_screen(tc, ac)
        elif state.active_page == 'certificate':
            render_certificate_screen(tc, ac, rgba_bg)
        else:
            render_data_screen(state.active_page, tc, ac, rgba_bg)

# --- Sub-Screens ---

def render_home_screen(tc, ac, rgba_bg):
    # Fetch live counts dynamically
    try:
        counts = DashboardRepository().get_counts()
    except Exception:
        counts = {"total_students": 0, "total_departments": 0, "total_courses": 0, "total_personnel": 0}
        
    with ui.column().classes('gap-1'):
        ui.label('Dashboard / لوحة التحكم').classes(f'text-2xl font-bold {tc["text_main"]} font-sans')
        ui.label('Welcome back to the Certificate Management System  /  مرحباً بك مجدداً في نظام إدارة الشهادات').classes(f'{tc["text_muted"]} text-sm')
    
    # KPI Grid (2x2)
    with ui.grid(columns=2).classes('w-full gap-6 mt-4'):
        kpi_data = [
            ('STUDENTS / الطلاب', str(counts.get('total_students', 0)), '👤'),
            ('DEPARTMENTS / الأقسام', str(counts.get('total_departments', 0)), '🏫'),
            ('COURSES / المواد', str(counts.get('total_courses', 0)), '📚'),
            ('PERSONNEL / الكوادر', str(counts.get('total_personnel', 0)), '👨‍💼')
        ]
        for title, val, emoji in kpi_data:
            with ui.row().classes(f'{tc["card_bg"]} p-5 rounded-xl items-center shadow-md border {tc["border_color"]} w-full gap-4'):
                with ui.element('div').classes('w-12 h-12 rounded-lg flex items-center justify-center') \
                    .style(f'background-color: {rgba_bg};'):
                    ui.label(emoji).classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label(title).classes(f'{tc["text_muted"]} text-xs font-bold tracking-wider font-sans')
                    ui.label(val).classes(f'{tc["text_main"]} text-2xl font-extrabold font-sans')

    # Quick Actions
    with ui.column().classes('w-full gap-3 mt-4'):
        ui.label('Quick Actions / إجراءات سريعة').classes(f'text-lg font-bold {tc["text_main"]} font-sans')
        with ui.row().classes('gap-3'):
            quick_actions = [
                ('👤 إضافة طالب جديد', 'students'),
                ('📜 إصدار وثيقة', 'certificate'),
                ('📚 إضافة مادة دراسية', 'courses')
            ]
            for action_label, target in quick_actions:
                ui.button(action_label, on_click=lambda t=target: state.set_page(t)) \
                    .style(f'background-color: {ac["hex"]}; text-transform: none; font-weight: bold; border-radius: 8px;') \
                    .classes('text-white px-5 py-2 text-sm shadow-md hover:brightness-95')

    # Recent Activity
    with ui.column().classes('w-full gap-3 mt-4'):
        with ui.column().classes(f'w-full {tc["card_bg"]} rounded-xl shadow-md border {tc["border_color"]} p-5 gap-3'):
            ui.label('Recent Activity / النشاط الأخير').classes(f'text-base font-bold {tc["text_main"]} mb-2 font-sans')
            
            try:
                activities = AuditRepository().get_audit_log(limit=3)
            except Exception:
                activities = []

            if activities:
                for i, act in enumerate(activities):
                    if i > 0:
                        ui.separator().classes(f'{tc["divider"]} my-1')
                    with ui.row().classes('w-full justify-between items-center py-1'):
                        ui.label(act.get('summary', '')).classes(f'{tc["text_main"]} font-medium text-sm font-sans w-2/3')
                        ui.label(act.get('action', '')).classes(f'{ac["text"]} font-bold text-xs font-sans text-center w-1/6')
                        ui.label(act.get('created_at', '')).classes(f'{tc["text_muted"]} text-xs text-right w-1/6 font-sans')
            else:
                ui.label('No activities registered yet.').classes(tc['text_muted'])

def render_settings_screen(tc, ac):
    ui.label('Settings / الإعدادات').classes(f'text-2xl font-bold {tc["text_main"]} font-sans')
    ui.label('Manage system preferences and appearance').classes(f'{tc["text_muted"]} text-sm')
    
    with ui.column().classes(f'w-full max-w-xl {tc["card_bg"]} rounded-xl shadow-md border {tc["border_color"]} p-6 gap-6 mt-6'):
        ui.label('Appearance / المظهر').classes(f'text-lg font-bold {tc["text_main"]} border-b pb-2').classes(tc['border_color'])
        
        # User details if any
        if state.current_user:
            ui.label(f"Active Account: {state.current_user.get('name_ar', '')} ({state.current_user.get('role', '')})").classes(f'{tc["text_main"]} text-sm')
            
        with ui.row().classes('w-full justify-between items-center'):
            ui.label('Theme Mode / المظهر').classes(f'{tc["text_main"]} text-sm')
            with ui.row().classes('bg-[#0E1117] p-1 rounded-lg gap-1 border border-gray-800'):
                for t in ['light', 'dark']:
                    is_active = (state.theme == t)
                    btn_style = 'bg-[#1F2937] text-white border border-white' if is_active else 'bg-transparent text-gray-400 hover:text-white'
                    ui.button(t, on_click=lambda t_val=t: state.set_theme(t_val)) \
                        .classes(f'{btn_style} px-4 py-1 text-xs font-bold lowercase rounded-md min-h-0 h-7') \
                        .props('unelevated')
                        
        with ui.row().classes('w-full justify-between items-center'):
            ui.label('Accent Color / لون المظهر المميز').classes(f'{tc["text_main"]} text-sm')
            with ui.row().classes('bg-[#0E1117] p-1 rounded-lg gap-1 border border-gray-800'):
                for color in ['blue', 'purple', 'emerald']:
                    is_active = (state.accent == color)
                    btn_style = 'bg-[#1F2937] text-white border border-white' if is_active else 'bg-transparent text-gray-400 hover:text-white'
                    ui.button(color, on_click=lambda c_val=color: state.set_accent(c_val)) \
                        .classes(f'{btn_style} px-4 py-1 text-xs font-bold lowercase rounded-md min-h-0 h-7') \
                        .props('unelevated')
                        
        with ui.row().classes('w-full justify-end my-4'):
            ui.button('Logout / تسجيل الخروج', on_click=state.logout) \
                .classes('bg-red-500 text-white rounded-lg px-6 py-2 hover:bg-red-600')

def clear_logs_action():
    try:
        AuditRepository().clear_audit_logs()
        ui.notify('Logs cleared successfully / تم مسح السجل بنجاح')
        render_workspace.refresh()
    except Exception as e:
        ui.notify(f'Failed to clear logs: {e}')

def render_data_screen(page_key, tc, ac, rgba_bg):
    # Header Title
    ar_title, en_title = SCREEN_HEADERS.get(page_key, (page_key, page_key))
    ui.label(ar_title).classes(f'text-2xl font-bold {tc["text_main"]} font-sans')
    ui.label(en_title).classes(f'{tc["text_muted"]} text-sm')
    
    # Search Input
    with ui.row().classes('w-full items-center gap-3 mt-4'):
        search_input = ui.input(placeholder='Search / بحث...').classes('w-64 bg-white dark:bg-gray-800 rounded-lg')
        search_input.value = state.search_query
        
        search_input.on('change', lambda e: state.set_search(e.value))
        ui.button('Search', on_click=lambda: state.set_search(search_input.value)) \
            .style(f'background-color: {ac["hex"]}; text-transform: none; border-radius: 8px;') \
            .classes('text-white px-4 py-2')
            
    # Load and filter data dynamically
    data = []
    columns = []
    
    try:
        if page_key == 'students':
            data = StudentRepository().get_all_paginated(limit=100, name_query=state.search_query)
            columns = [
                {'name': 'id', 'label': 'ID / المعرف', 'field': 'id', 'required': True, 'align': 'left'},
                {'name': 'full_name_ar', 'label': 'الاسم الكامل (عربي)', 'field': 'full_name_ar', 'align': 'right'},
                {'name': 'full_name_en', 'label': 'Full Name (EN)', 'field': 'full_name_en', 'align': 'left'},
                {'name': 'admission_year', 'label': 'سنة القبول', 'field': 'admission_year', 'align': 'center'},
                {'name': 'graduation_year', 'label': 'سنة التخرج', 'field': 'graduation_year', 'align': 'center'},
                {'name': 'average', 'label': 'المعدل', 'field': 'average', 'align': 'center'},
            ]
        elif page_key == 'departments':
            data = DepartmentRepository().get_all()
            if state.search_query:
                q = state.search_query.lower()
                data = [d for d in data if q in str(d.get('name_ar','')).lower() or q in str(d.get('name_en','')).lower()]
            columns = [
                {'name': 'id', 'label': 'ID / المعرف', 'field': 'id', 'align': 'left'},
                {'name': 'name_ar', 'label': 'القسم (عربي)', 'field': 'name_ar', 'align': 'right'},
                {'name': 'name_en', 'label': 'Department (EN)', 'field': 'name_en', 'align': 'left'},
                {'name': 'college_name_ar', 'label': 'الكلية', 'field': 'college_name_ar', 'align': 'right'},
                {'name': 'study_years', 'label': 'سنوات الدراسة', 'field': 'study_years', 'align': 'center'}
            ]
        elif page_key == 'courses':
            data = CourseRepository().get_all()
            if state.search_query:
                q = state.search_query.lower()
                data = [c for c in data if q in str(c.get('name_ar','')).lower() or q in str(c.get('name_en','')).lower()]
            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'align': 'left'},
                {'name': 'name_ar', 'label': 'المادة (عربي)', 'field': 'name_ar', 'align': 'right'},
                {'name': 'name_en', 'label': 'Course (EN)', 'field': 'name_en', 'align': 'left'},
                {'name': 'credit_hours', 'label': 'الوحدات', 'field': 'credit_hours', 'align': 'center'},
                {'name': 'stage_number', 'label': 'المرحلة', 'field': 'stage_number', 'align': 'center'},
                {'name': 'dept_name_ar', 'label': 'القسم', 'field': 'dept_name_ar', 'align': 'right'}
            ]
        elif page_key == 'personnel':
            data = PersonnelRepository().get_all()
            if state.search_query:
                q = state.search_query.lower()
                data = [p for p in data if q in str(p.get('name_ar','')).lower() or q in str(p.get('username','')).lower()]
            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'align': 'left'},
                {'name': 'username', 'label': 'اسم المستخدم', 'field': 'username', 'align': 'left'},
                {'name': 'name_ar', 'label': 'الاسم (عربي)', 'field': 'name_ar', 'align': 'right'},
                {'name': 'role', 'label': 'الصلاحية', 'field': 'role', 'align': 'center'},
                {'name': 'is_active', 'label': 'نشط', 'field': 'is_active', 'align': 'center'}
            ]
        elif page_key == 'orders':
            data = GraduationOrderRepository().get_all(limit=50)
            if state.search_query:
                q = state.search_query.lower()
                data = [o for o in data if q in str(o.get('order_number','')).lower()]
            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'align': 'left'},
                {'name': 'order_number', 'label': 'رقم الأمر', 'field': 'order_number', 'align': 'left'},
                {'name': 'order_date', 'label': 'تاريخ الأمر', 'field': 'order_date', 'align': 'center'},
                {'name': 'dept_name_ar', 'label': 'القسم', 'field': 'dept_name_ar', 'align': 'right'},
                {'name': 'linked_count', 'label': 'عدد الطلاب', 'field': 'linked_count', 'align': 'center'}
            ]
        elif page_key == 'history':
            data = AuditRepository().get_audit_log(limit=100)
            if state.search_query:
                q = state.search_query.lower()
                data = [h for h in data if q in str(h.get('summary','')).lower()]
            columns = [
                {'name': 'created_at', 'label': 'التاريخ / Date', 'field': 'created_at', 'align': 'left'},
                {'name': 'table_name', 'label': 'الجدول / Component', 'field': 'table_name', 'align': 'center'},
                {'name': 'action', 'label': 'الإجراء / Action', 'field': 'action', 'align': 'center'},
                {'name': 'summary', 'label': 'التفاصيل / Details', 'field': 'summary', 'align': 'right'}
            ]
            
            # Clear activity log option
            with ui.row().classes('w-full justify-end my-2'):
                ui.button('Clear Activity Logs / مسح السجل', on_click=clear_logs_action) \
                    .classes('bg-red-500 text-white rounded-lg px-4 py-2 hover:bg-red-650')
    except Exception as e:
        print(f"Error querying page {page_key}: {e}")
        data = []
        
    if data:
        with ui.element('div').classes('w-full overflow-x-auto rounded-xl shadow-md border').classes(tc['border_color']):
            ui.table(columns=columns, rows=data, row_key='id').classes('w-full bg-white dark:bg-[#222631]')
    else:
        with ui.column().classes('w-full items-center p-8 bg-white dark:bg-[#222631] rounded-xl border').classes(tc['border_color']):
            ui.label('No records found / لا توجد سجلات').classes(f'{tc["text_muted"]} font-bold')

# --- Certificate Screen Stateful Operations ---
class CertificateState:
    def __init__(self):
        self.selected_student_id = None
        self.certificate_data = None

    def select_student(self, sid):
        self.selected_student_id = sid
        if sid:
            try:
                self.certificate_data = CertificateRepository().get_full_certificate_data(sid)
            except Exception as e:
                self.certificate_data = None
                print(f"Error loading certificate: {e}")
        else:
            self.certificate_data = None
        render_workspace.refresh()

cert_state = CertificateState()

def render_certificate_screen(tc, ac, rgba_bg):
    if cert_state.selected_student_id is None:
        # Search panel
        with ui.column().classes('w-full gap-4'):
            ui.label('Select Student / اختر طالب').classes(f'text-lg font-bold {tc["text_main"]} font-sans')
            with ui.row().classes('w-full items-center gap-3'):
                search_input = ui.input(placeholder='Search student name / ابحث عن اسم الطالب...').classes('w-96 bg-white dark:bg-gray-800 rounded-lg')
                search_btn = ui.button('Search / بحث') \
                    .style(f'background-color: {ac["hex"]}; text-transform: none; border-radius: 8px;') \
                    .classes('text-white')
            
            results_container = ui.column().classes('w-full gap-2 mt-4')
            
            async def do_search():
                results_container.clear()
                q = (search_input.value or '').strip()
                if q:
                    try:
                        students = await run.io_bound(StudentRepository().get_all_paginated, limit=15, name_query=q)
                        if students:
                            with results_container:
                                for s in students:
                                    with ui.row().classes(f'w-full p-4 {tc["card_bg"]} rounded-xl border {tc["border_color"]} justify-between items-center cursor-pointer hover:bg-gray-200/50') \
                                        .on('click', lambda s_id=s['id']: cert_state.select_student(s_id)):
                                        ui.label(s.get('full_name_ar', '')).classes(f'font-bold {tc["text_main"]}')
                                        ui.label(s.get('full_name_en', '')).classes(f'{tc["text_muted"]} text-sm')
                                        ui.label(s.get('dept_name_ar', '')).classes(f'{tc["text_muted"]} text-sm')
                        else:
                            with results_container:
                                ui.label('No students found / لم يتم العثور على طلاب').classes('text-red-500 font-bold')
                    except Exception as e:
                        print(f"Certificate Search error: {e}")
            
            search_btn.on('click', do_search)
            search_input.on('keydown.enter', do_search)
    else:
        # Certificate preview document
        ui.button('← Back to Search / رجوع للبحث', on_click=lambda: cert_state.select_student(None)) \
            .classes('bg-gray-500 text-white rounded-lg px-4 py-2 mt-2 hover:bg-gray-600')
            
        data = cert_state.certificate_data
        if data:
            with ui.column().classes('w-full mt-6 bg-white dark:bg-[#1E222B] p-8 rounded-2xl border-4 border-double border-gray-400 gap-6 shadow-lg max-w-4xl self-center text-center'):
                # Bilingual Headers
                with ui.row().classes('w-full justify-between items-center px-4'):
                    with ui.column().classes('items-start text-left'):
                        ui.label(data.get('univ_name_en', 'University Name')).classes('font-bold text-sm text-gray-800 dark:text-gray-100')
                        ui.label(data.get('college_name_en', 'College Name')).classes('text-xs text-gray-500 dark:text-gray-400')
                    with ui.column().classes('items-end text-right'):
                        ui.label(data.get('univ_name_ar', 'اسم الجامعة')).classes('font-bold text-sm text-gray-800 dark:text-gray-100')
                        ui.label(data.get('college_name_ar', 'اسم الكلية')).classes('text-xs text-gray-500 dark:text-gray-400')
                
                ui.separator().classes('bg-gray-400 my-2')
                
                ui.label('وثيقة تخرج  /  Graduation Certificate').classes('text-xl font-extrabold text-gray-800 dark:text-gray-100 font-sans my-4')
                
                # Document Core Body Text
                with ui.column().classes('w-full gap-4 px-4 text-justify leading-relaxed'):
                    ui.label(
                        f"يشهد مجلس الكلية بأن الطالب/الطالبة ({data.get('full_name_ar', '')})، "
                        f"المولود في ({data.get('birthplace_ar') or data.get('birthplace_other') or 'العراق'})، "
                        f"قد تخرج في قسم ({data.get('dept_name_ar', '')}) وحصل على شهادة البكالوريوس بتقدير "
                        f"({data.get('average', '0')}) لسنة التخرج ({data.get('graduation_semester', '')} / {data.get('graduation_date', '')[:4] if data.get('graduation_date') else ''})."
                    ).classes('text-base text-gray-800 dark:text-gray-200 font-medium')
                    
                    ui.label(
                        f"The College Council certifies that ({data.get('full_name_en', '')}), "
                        f"born in ({data.get('birthplace_en') or data.get('birthplace_other') or 'Iraq'}), "
                        f"has graduated from the Department of ({data.get('dept_name_en', '')}) and was awarded the Bachelor Degree "
                        f"with a GPA of ({data.get('average', '0')}) for the academic period ({data.get('graduation_semester', '')} / {data.get('graduation_date', '')[:4] if data.get('graduation_date') else ''})."
                    ).classes('text-sm text-gray-600 dark:text-gray-300 italic')
                
                # Signatories
                with ui.row().classes('w-full justify-around mt-12 gap-8'):
                    for sig in data.get('front_signatories', []):
                        with ui.column().classes('items-center'):
                            ui.label(sig.get('name_ar', '')).classes('font-bold text-sm text-gray-800 dark:text-gray-100')
                            ui.label(sig.get('role', '')).classes('text-xs text-gray-500 dark:text-gray-400')
        else:
            with ui.column().classes('w-full items-center p-8 bg-red-100 dark:bg-red-900/20 rounded-xl mt-6'):
                ui.label('Error: Could not retrieve certificate data / خطأ في استرداد بيانات الوثيقة').classes('text-red-500 font-bold')

# --- Main Page Frame ---
def render_main_shell():
    tc = theme_colors[state.theme]
    ac = accent_colors[state.accent]
    
    with ui.column().classes('w-full min-h-screen bg-[#0E1117] items-center justify-between p-6 gap-6'):
        # Header slot
        render_header()
        
        # Dual panel layout
        with ui.row().classes(f'w-full max-w-5xl rounded-2xl overflow-hidden shadow-2xl flex-nowrap gap-0 border {tc["border_color"]}'):
            # Navigation Sidebar
            render_sidebar()
            
            # Active screen slot
            render_workspace()

        # Bottom Controls Panel
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

            # Controls Toggles Row
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

# --- App Render Switcher ---
@ui.refreshable
def render_app():
    if state.current_user is None:
        render_login_screen()
    else:
        render_main_shell()

# Render initial view
render_app()

# --- Network Poller (Using Asyncio and NiceGUI io_bound) ---
async def check_network_poller():
    try:
        now_online = await run.io_bound(check_network_status)
        state.set_online(now_online)
    except Exception as exc:
        system_logger.error("Network check exception: %s", exc)

ui.timer(8.0, check_network_poller)

# --- FastAPI Windows Service Restarter ---
def _restart_fastapi_service_async() -> None:
    def run_restart():
        try:
            import subprocess
            system_logger.info("Restarting FastAPI Windows Service asynchronously...")
            subprocess.run(
                ["cmd", "/c", "net stop FastAPICertificateManager && net start FastAPICertificateManager"],
                capture_output=True,
                shell=True
            )
            system_logger.info("FastAPI Windows Service restart sequence completed.")
        except Exception as exc:
            system_logger.warning("Could not restart FastAPI service automatically: %s", exc)

    import threading
    threading.Thread(target=run_restart, daemon=True, name="ServiceRestarter").start()

# --- Run nicegui_main.py ---
try:
    _restart_fastapi_service_async()
except Exception as e:
    system_logger.warning("Could not launch service restart sequence: %s", e)

try:
    import webview
    has_webview = True
except ImportError:
    has_webview = False

if has_webview:
    ui.run(native=True, window_size=(1024, 768), title="Certificate Manager Dashboard", port=8060)
else:
    print("Native mode not supported because 'pywebview' is not installed. Falling back to browser-based mode on port 8060.")
    ui.run(title="Certificate Manager Dashboard", port=8060)
