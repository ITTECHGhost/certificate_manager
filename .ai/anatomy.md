# Project Anatomy

- `main.py`: The main entry point. Initializes the CTk window, sidebar, header bar (with network status indicator), screen navigation, and the 8-second network polling loop (`_poll_network`).
- `db.py`: MySQL connection factory (`get_connection`), schema self-healing migrations (`init_db`), grade helper, and backup/restore via `mysqldump`/`mysql` CLI.
- `sync_engine.py`: Offline sync engine. Manages the local SQLite cache (`local_cache.db`) with: network status flag (`is_online`/`set_online`/`check_network_status`), outbound sync queue (temp negative IDs → MySQL), inbound sync (`pull_mysql_to_sqlite` replicates 12 MySQL tables), SP result cache (`cache_read_result`/`get_cached_read`), and direct SQLite query helpers (`sqlite_read_all`/`sqlite_read_one`).
- `config.py`: Application configuration — theme colors (`AppColors`), fonts (`AppFonts`), layout sizes (`AppSizes`), navigation items, screen headers, and user preference refresh.
- `data/repositories.py`: Data Access Layer. All MySQL Stored Procedure calls go through `BaseRepository` with automatic online/offline routing. Contains `OfflineModeError`, and per-entity repositories: `SettingsRepository`, `PersonnelRepository`, `DepartmentRepository`, `StudySystemRepository`, `CourseRepository`, `StudentRepository`, `AcademicPeriodRepository`, `EnrollmentRepository`, `CertificateRepository`, `GraduationOrderRepository`, `ThesisRepository`, `StudentSupervisorRepository`, `AuditRepository`.
- `screens/`: UI screens — `login_screen.py`, `home_screen.py`, `students_screen.py`, `courses_screen.py`, `personnel_screen.py`, `graduation_orders_screen.py`, `order_students_screen.py`, `history_screen.py`, `certificate_screen.py`, `settings_screen.py`.
- `ui/`: Reusable UI components and widget wrappers (built on `customtkinter`). Includes `base_screen.py`.
- `templets/`: Word document templates (`.docx`) for certificate generation.
- `themes/`: JSON theme files for `customtkinter` styling.
- `tools/`: Utility scripts — `migrate_mysql.py` (SQLite→MySQL migration).
- `local_cache.db`: Auto-generated SQLite database for offline mode. Contains sync queue, temp ID counter, SP result cache, and replica tables for all major MySQL tables.
