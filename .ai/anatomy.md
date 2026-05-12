# Project Anatomy

- `main.py`: The main entry point for the application. Initializes the main window and manages screen navigation.
- `db.py`: Handles database connection setup and core database operations.
- `config.py`: Contains application configuration variables, theme setup, and layout constraints.
- `screens/`: Directory containing all major UI screens for the application (e.g., login, student management, course management, certificate generation).
- `data/queries.py`: Centralized location for SQL queries used throughout the application to interact with the database.
- `ui/`: Contains custom, reusable UI components and widget wrappers (built on top of `customtkinter`).
- `templets/`: Word document templates (`.docx`) used for generating certificates.
- `themes/`: JSON theme files used for `customtkinter` styling.
- `tools/`: Utility scripts and helper functions.
