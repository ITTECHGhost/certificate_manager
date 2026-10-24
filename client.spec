# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# client.spec — PyInstaller Specification for Certificate Manager Client
# =============================================================================

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect full dependency assets for NiceGUI and PyWebView
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all('nicegui')
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

# Application static assets and configuration
app_datas = [
    ('templets', 'templets'),
    ('sql', 'sql'),
    ('nicegui_ui', 'nicegui_ui'),
    ('csit.png', '.'),
    ('server_config.json', '.'),
    ('certs/college_ca.crt', 'certs'),
    ('scripts/apply_patch.bat', 'scripts'),
]

datas = nicegui_datas + webview_datas + app_datas
binaries = nicegui_binaries + webview_binaries

hiddenimports = (
    nicegui_hiddenimports
    + webview_hiddenimports
    + [
        'services.updater',
        'services.template_sync',
        'services.excel_import_service',
        'nicegui_screens.login_screen',
        'nicegui_screens.dashboard_screen',
        'nicegui_screens.settings_screen',
        'nicegui_screens.student_bulk_import_view',
        'nicegui_ui.ui_components',
        'nicegui_ui.ui_theme',
        'nicegui_ui.state',
        'sync_engine',
        'data.repositories',
        'api_config',
        'utils.health_check',
        'utils.logger',
        'docx',
        'openpyxl',
        'psutil',
        'requests',
        'sqlite3',
    ]
)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CertificateManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='csit.png'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CertificateManager'
)
