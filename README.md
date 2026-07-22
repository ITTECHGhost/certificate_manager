# Certificate Manager Application
A complete management system for academic certificates, powered by a robust Python backend and a modern web-based UI wrapped as a native desktop application.

## Architecture

The system is built on a multi-tier architecture to separate concerns, ensure data reliability, and provide a fluid user interface.

### 1. Presentation Layer (NiceGUI)
- **Framework**: [NiceGUI](https://nicegui.io/)
- **Entry Point**: `N_main.py`
- **Execution**: The UI launches as a native desktop window (using PyWebView) while utilizing modern web technologies (Vue3, TailwindCSS, Quasar) for styling and layout.
- **Port Mapping**: The NiceGUI frontend operates on **Port 2323**.
- **Structure**:
  - `nicegui_screens/`: Contains the individual pages (Login, Dashboard, Settings, etc.).
  - `nicegui_ui/`: Contains the UI component factory (`ui_components.py`), theme configuration (`ui_theme.py`), and session state management (`state.py`).

### 2. API & Service Layer (FastAPI)
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Entry Points**: 
  - `certificate_manager_api/main.py`
  - Start Script: `certificate_manager_api/start_server.bat`
- **Port Mapping**: The FastAPI server operates on **Port 2030**.
- **Responsibility**: Provides RESTful endpoints for integration, external system syncing, and offloading heavy computational tasks.

### 3. Data Access Layer (Repositories)
- **Namespace**: `data/repositories/`
- **Responsibility**: Implements the Repository Pattern to abstract database operations (MySQL/SQLite). Repositories handle fetching, authenticating, searching, and creating records (e.g., `StudentRepository`, `AuthRepository`).

### 4. Database & Sync Engine
- **Primary Database**: MySQL (running locally via XAMPP on Port 3306) or SQLite (for offline redundancy).
- **Sync Engine**: `sync_engine.py` provides offline-first capabilities, allowing the application to cache data locally and synchronize with the master MySQL server when network connectivity is restored.

---

## How to Run the Application

### 1. Start the API Server
Before launching the main application, ensure the API backend is running:
1. Navigate to `certificate_manager_api/`.
2. Run `start_server.bat`. This will launch FastAPI on `http://0.0.0.0:2030` in the background.

### 2. Start the Application UI
The user interface is initiated from the project root:
```bash
python N_main.py
```
*(Note: Running `python main.py` is also supported as a lightweight launcher that redirects seamlessly to `N_main.py`.)*

---

## Legacy Code (`old design/`)
To preserve historical design iterations and maintain a clean active workspace, all legacy user interfaces have been archived in the `old design/` directory. This includes:
- **CustomTkinter & Tkinter screens** (`ctk_screens/`, `screens/`)
- **Legacy UI Widgets** (`ui/`, `legacy_ui/`)
- Previous standalone UI tests and the original CustomTkinter `main_ctk.py`.
These files are not utilized in the current NiceGUI architecture.
