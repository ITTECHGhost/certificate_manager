# Certificate Manager

Management of academic records and official certificates for the college: students, courses,
graduation orders, Word-template certificates (Arabic/English), printing, and an offline mode.

## Parts

| Part | Folder / file | Runs on |
|---|---|---|
| Client program (NiceGUI, native window via pywebview) | `main.py`, `nicegui_screens/`, `nicegui_ui/`, `data/`, `services/`, `utils/`, `sync_engine.py` | every staff laptop, installed with `CertificateManager-Setup-<version>.exe` |
| API server (FastAPI, Windows service, port 2030) | `certificate_manager_api/` | the server laptop, installed with the server bundle's `setup_server.bat` |
| Database | MySQL 8 (`sql/schema.sql`, `sql/SP.sql`, changes in `sql/fixes/`) | the server laptop |
| Offline cache | SQLite `local_cache.db` | each client's data folder |

The client never talks to MySQL directly. Everything goes through the API (`api_client.py`), which a test enforces.

## Where files live

`app_paths.py` decides where the program reads and writes:
- **From source:** the project folder, as always.
- **Installed:** the program sits in `%LOCALAPPDATA%\Programs\CertificateManager`, and all data
  (cache, logs, templates, certificates, `server_config.json`) is in `%LOCALAPPDATA%\CertificateManager`.

## Developer quick start

```cmd
py -3 -m pip install -r requirements-dev.txt
certificate_manager_api\start_server.bat      :: API in a visible console (needs certificate_manager_api\db_config.json)
py -3 main.py                                 :: client (add --web for browser mode on port 2323)
py -3 -m pytest                               :: tests; py -3 -m pytest -m mysql for read-only API comparisons
```

## Releases

1. Raise `APP_VERSION` in `app_version.py`.
2. `scripts\build_release.bat`: tests, PyInstaller build, update ZIP, Inno Setup installer, checksums.
3. `powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1`: the server bundle.

Full instructions: `docs/installation_guide.md` and `certificate_manager_api/SERVER_SETUP_GUIDE.md`.
The refactor plan and its step-by-step runbooks are in `docs/superpowers/plans/`.

## Legacy code

Old CustomTkinter screens, scratch scripts and SQL dumps are in `old/` (dumps and old copies holding
passwords or student data are kept on disk only, never in git).
