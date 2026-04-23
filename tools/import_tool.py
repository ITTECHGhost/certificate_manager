# =============================================================================
# tools/import_tool.py — Database Import Tool
# =============================================================================
#
# PURPOSE:
#   A standalone utility (run separately from main.py) to import data from
#   an existing SQLite database into certificate_manager.db.
#
# HOW TO RUN:
#   python tools/import_tool.py
#   (run from inside the certificate_manager\ folder)
#
# WHAT IT DOES:
#   1. Shows all tables in the source database
#   2. Lets you preview each table's contents
#   3. Provides a field-mapping import for students
#   4. Shows a log of what was imported and what was skipped
#
# SUPPORTED IMPORT SOURCES:
#   - Any SQLite .db or .sqlite file
#
# NOTE:
#   Before importing students, the destination database must already have:
#   - At least one department (use main.py → Departments to add one)
#   - Countries and governorates (already seeded by db.py)
#
# =============================================================================

import sys
import os
import sqlite3
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog

# Make sure project root is on the path so we can import db and queries
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_connection, init_db

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

FONT_FAMILY = "Arial"


# =============================================================================
# Import Logic (no UI)
# =============================================================================

def get_source_tables(source_path: str) -> list[str]:
    """Return a list of all table names in the source database."""
    conn = sqlite3.connect(source_path)
    tables = [
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    conn.close()
    return tables


def get_source_columns(source_path: str, table: str) -> list[str]:
    """Return the column names of a table in the source database."""
    conn = sqlite3.connect(source_path)
    cursor = conn.execute(f"SELECT * FROM [{table}] LIMIT 0")
    cols = [desc[0] for desc in cursor.description]
    conn.close()
    return cols


def get_source_preview(source_path: str, table: str, limit: int = 20) -> list[dict]:
    """Return up to `limit` rows from a source table as list of dicts."""
    conn = sqlite3.connect(source_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM [{table}] LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_destination_departments() -> list[dict]:
    """Return all departments from the destination database."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name_ar, name_en FROM departments").fetchall()
    return [dict(r) for r in rows]


def get_destination_country_id(iso_or_name: str) -> int | None:
    """Look up a country by ISO code or English name. Returns its ID or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM countries WHERE iso_code = ? OR name_en LIKE ?",
            (iso_or_name.upper(), f"%{iso_or_name}%")
        ).fetchone()
    return row["id"] if row else None


def get_destination_governorate_id(name: str) -> int | None:
    """Look up a governorate by Arabic or English name. Returns its ID or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM governorates WHERE name_ar LIKE ? OR name_en LIKE ?",
            (f"%{name}%", f"%{name}%")
        ).fetchone()
    return row["id"] if row else None


def import_students(
    source_path: str,
    source_table: str,
    mapping: dict[str, str],        # destination_field → source_column
    default_dept_id: int,
    default_nationality_id: int,
    log_callback,                   # Callable[[str], None]
) -> tuple[int, int]:               # (imported_count, skipped_count)
    """
    Import student rows from source_table into the destination students table.

    Args:
        source_path:            Path to the source .db file.
        source_table:           Table name in the source database.
        mapping:                Maps destination fields to source column names.
                                Required keys: full_name_ar, date_of_birth
                                Optional: full_name_en, admission_year,
                                          study_type, average, graduation_date
        default_dept_id:        Department ID to assign if not in source data.
        default_nationality_id: Country ID to assign if not in source data.
        log_callback:           Function to call with status messages.

    Returns:
        Tuple (imported_count, skipped_count).
    """
    source_rows = get_source_preview(source_path, source_table, limit=99999)
    imported = 0
    skipped  = 0

    with get_connection() as conn:
        for row in source_rows:
            try:
                # Required fields
                name_ar = str(row.get(mapping.get("full_name_ar", ""), "") or "").strip()
                if not name_ar:
                    log_callback(f"⚠️  Skipped row with no Arabic name: {dict(row)}")
                    skipped += 1
                    continue

                dob = str(row.get(mapping.get("date_of_birth", ""), "") or "").strip()
                if not dob:
                    dob = "2000-01-01"      # fallback date if not in source

                # Optional fields with sensible defaults
                name_en        = str(row.get(mapping.get("full_name_en", ""),        "") or "").strip()
                admission_year = row.get(mapping.get("admission_year", ""),          None)
                study_type     = str(row.get(mapping.get("study_type",  ""),  "morning") or "morning")
                average        = row.get(mapping.get("average",         ""),          None)
                grad_date      = str(row.get(mapping.get("graduation_date", ""),     "") or "").strip() or None
                grad_sem       = str(row.get(mapping.get("graduation_semester", ""),"") or "").strip() or None

                # Normalise study_type
                if study_type not in ("morning", "evening"):
                    study_type = "morning"

                # Normalise average
                if average is not None:
                    try:
                        average = int(float(average))
                        if not (50 <= average <= 100):
                            average = None
                    except (ValueError, TypeError):
                        average = None

                # Normalise admission_year
                if admission_year is not None:
                    try:
                        admission_year = int(admission_year)
                    except (ValueError, TypeError):
                        admission_year = 2020

                # Determine birthplace
                birthplace_id    = None
                birthplace_other = "غير محدد"      # default for unknown birthplace

                conn.execute(
                    "INSERT INTO students "
                    "(full_name_ar, full_name_en, date_of_birth, "
                    " birthplace_id, birthplace_other, nationality_id, "
                    " department_id, admission_year, study_type, "
                    " graduation_date, graduation_semester, average) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (name_ar, name_en or name_ar, dob,
                     birthplace_id, birthplace_other, default_nationality_id,
                     default_dept_id, admission_year or 2020, study_type,
                     grad_date, grad_sem or None, average)
                )
                imported += 1
                log_callback(f"✅  Imported: {name_ar}")

            except sqlite3.Error as e:
                log_callback(f"❌  Error on row {dict(row)}: {e}")
                skipped += 1

        conn.commit()

    return imported, skipped


# =============================================================================
# Import Tool Window
# =============================================================================

class ImportToolWindow(ctk.CTk):
    """Main window of the import tool."""

    def __init__(self) -> None:
        super().__init__()
        self.title("أداة الاستيراد  —  Import Tool")
        self.geometry("900x650")
        self.minsize(800, 550)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Ensure destination DB is ready
        init_db()

        self._source_path: str | None = None
        self._source_table: str | None = None
        self._source_columns: list[str] = []
        self._mapping_dropdowns: dict[str, ctk.CTkOptionMenu] = {}

        self._build()

    def _build(self) -> None:
        self._build_top_bar()
        self._build_main_area()

    def _build_top_bar(self) -> None:
        """File picker and table selector at the top."""
        bar = ctk.CTkFrame(self, height=60, corner_radius=0,
                            fg_color=("gray90", "gray18"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            bar,
            text="📂  اختر ملف قاعدة البيانات  /  Choose Source DB",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            command=self._choose_file,
        ).grid(row=0, column=0, padx=12, pady=10)

        self._file_label = ctk.CTkLabel(
            bar,
            text="لم يتم اختيار ملف  —  No file selected",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="gray55",
            anchor="w",
        )
        self._file_label.grid(row=0, column=1, sticky="w", padx=8)

        self._table_menu = ctk.CTkOptionMenu(
            bar,
            values=["—"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            width=200,
            command=self._on_table_selected,
        )
        self._table_menu.set("اختر جدول  /  Select Table")
        self._table_menu.grid(row=0, column=2, padx=12, pady=10)

    def _build_main_area(self) -> None:
        """Three-column area: preview | mapping | log."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        main.grid_columnconfigure(0, weight=2)  # preview
        main.grid_columnconfigure(1, weight=1)  # mapping
        main.grid_columnconfigure(2, weight=1)  # log
        main.grid_rowconfigure(1, weight=1)

        # --- Column headers ---
        for col, text in enumerate([
            "معاينة البيانات  —  Data Preview",
            "تعيين الحقول  —  Field Mapping",
            "سجل الاستيراد  —  Import Log",
        ]):
            ctk.CTkLabel(
                main, text=text,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                anchor="w",
            ).grid(row=0, column=col, sticky="w", padx=(0, 8), pady=(0, 6))

        # Preview area
        self._preview = ctk.CTkTextbox(
            main,
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled",
            wrap="none",
        )
        self._preview.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        # Mapping area (scrollable)
        self._mapping_scroll = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self._mapping_scroll.grid(row=1, column=1, sticky="nsew", padx=(0, 8))
        self._mapping_scroll.grid_columnconfigure(0, weight=1)
        self._build_mapping_area(self._mapping_scroll)

        # Log area
        self._log = ctk.CTkTextbox(
            main,
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled",
        )
        self._log.grid(row=1, column=2, sticky="nsew")

        # Import button at the bottom
        ctk.CTkButton(
            self,
            text="▶  استيراد الطلاب  /  Import Students",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            height=42,
            command=self._run_import,
        ).grid(row=2, column=0, pady=12, padx=14, sticky="ew")

    def _build_mapping_area(self, parent: ctk.CTkScrollableFrame) -> None:
        """
        Dropdowns that map each destination field to a source column.
        Only shown once a source table is selected.
        """
        # Destination fields the importer understands
        dest_fields = [
            ("full_name_ar",        "الاسم بالعربية  /  Arabic Name  *"),
            ("full_name_en",        "الاسم بالإنكليزية  /  English Name"),
            ("date_of_birth",       "تاريخ الميلاد  /  Date of Birth"),
            ("admission_year",      "سنة القبول  /  Admission Year"),
            ("study_type",          "نوع الدراسة  /  Study Type"),
            ("average",             "المعدل  /  Average"),
            ("graduation_date",     "تاريخ التخرج  /  Graduation Date"),
            ("graduation_semester", "فصل التخرج  /  Graduation Semester"),
        ]

        ctk.CTkLabel(
            parent,
            text="عيّن عمود المصدر لكل حقل\n(* = مطلوب)\nMap source column to each field\n(* = required)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color="gray55",
            justify="right",
        ).grid(row=0, column=0, sticky="e", pady=(0, 10))

        for row_idx, (field_key, field_label) in enumerate(dest_fields):
            ctk.CTkLabel(
                parent,
                text=field_label,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                anchor="e",
            ).grid(row=row_idx * 2 + 1, column=0, sticky="e", pady=(4, 0))

            menu = ctk.CTkOptionMenu(
                parent,
                values=["— لا تستورد / skip —"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                height=28,
            )
            menu.grid(row=row_idx * 2 + 2, column=0, sticky="ew", pady=(0, 2))
            self._mapping_dropdowns[field_key] = menu

        # Default department selector
        ctk.CTkLabel(
            parent,
            text="القسم الافتراضي  /  Default Department  *",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            anchor="e",
        ).grid(row=len(dest_fields) * 2 + 1, column=0, sticky="e", pady=(12, 0))

        depts = get_destination_departments()
        dept_labels = [f"{d['name_ar']}  /  {d['name_en']}" for d in depts] or ["لا يوجد أقسام  —  No departments"]
        self._dept_menu = ctk.CTkOptionMenu(
            parent,
            values=dept_labels,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            height=28,
        )
        self._dept_menu.grid(row=len(dest_fields) * 2 + 2, column=0, sticky="ew")
        self._dept_objects = depts

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    def _choose_file(self) -> None:
        """Open a file dialog to select the source SQLite database."""
        path = filedialog.askopenfilename(
            title="اختر ملف قاعدة البيانات  —  Select Database File",
            filetypes=[("SQLite files", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")],
        )
        if not path:
            return

        self._source_path = path
        self._file_label.configure(text=path)

        tables = get_source_tables(path)
        if tables:
            self._table_menu.configure(values=tables)
            self._table_menu.set(tables[0])
            self._on_table_selected(tables[0])
        else:
            self._table_menu.configure(values=["لا توجد جداول  —  No tables found"])

    def _on_table_selected(self, table: str) -> None:
        """Load column names and preview data when user selects a table."""
        if not self._source_path or table == "—":
            return

        self._source_table = table
        self._source_columns = get_source_columns(self._source_path, table)

        col_options = ["— لا تستورد / skip —"] + self._source_columns

        # Update all mapping dropdowns with the new column options
        for menu in self._mapping_dropdowns.values():
            menu.configure(values=col_options)
            menu.set(col_options[0])

        # Auto-map common field names intelligently
        auto_map = {
            "full_name_ar":    ["name_ar", "arabic_name", "full_name_ar", "student_name_ar", "اسم"],
            "full_name_en":    ["name_en", "english_name", "full_name_en", "student_name_en"],
            "date_of_birth":   ["dob", "date_of_birth", "birth_date", "birthdate"],
            "admission_year":  ["admission_year", "year", "enroll_year", "start_year"],
            "average":         ["average", "gpa", "grade_avg", "final_average"],
            "graduation_date": ["graduation_date", "grad_date", "graduate_date"],
        }
        for dest_field, candidates in auto_map.items():
            menu = self._mapping_dropdowns.get(dest_field)
            if not menu:
                continue
            for col in self._source_columns:
                if col.lower() in [c.lower() for c in candidates]:
                    menu.set(col)
                    break

        # Show preview
        self._show_preview()

    def _show_preview(self) -> None:
        """Display first 20 rows of the selected table in the preview box."""
        if not self._source_path or not self._source_table:
            return

        rows = get_source_preview(self._source_path, self._source_table, limit=20)

        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")

        if not rows:
            self._preview.insert("end", "لا توجد بيانات  —  No data found")
        else:
            # Header
            cols = list(rows[0].keys())
            self._preview.insert("end", "  |  ".join(cols) + "\n")
            self._preview.insert("end", "-" * 80 + "\n")
            for row in rows:
                self._preview.insert("end", "  |  ".join(str(v or "") for v in row.values()) + "\n")

        self._preview.configure(state="disabled")

    def _run_import(self) -> None:
        """Collect mapping choices and run the import."""
        if not self._source_path or not self._source_table:
            self._log_message("❌  يرجى اختيار ملف وجدول أولاً.  Please choose a file and table first.")
            return

        if not self._dept_objects:
            self._log_message("❌  يجب إضافة قسم في التطبيق أولاً.  Add a department in main.py first.")
            return

        # Build mapping dict from dropdown selections
        mapping = {}
        skip_val = "— لا تستورد / skip —"
        for field, menu in self._mapping_dropdowns.items():
            val = menu.get()
            if val != skip_val:
                mapping[field] = val

        # Get selected department ID
        dept_label  = self._dept_menu.get()
        dept_id     = next(
            (d["id"] for d in self._dept_objects
             if f"{d['name_ar']}  /  {d['name_en']}" == dept_label),
            None
        )
        if not dept_id:
            self._log_message("❌  لم يتم تحديد القسم.  Department not found.")
            return

        # Default nationality = Iraq (IQ)
        nat_id = None
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM countries WHERE iso_code='IQ'").fetchone()
            if row:
                nat_id = row["id"]
        if not nat_id:
            self._log_message("❌  لم يتم العثور على العراق في قاعدة البيانات.")
            return

        self._log_message("▶  بدء الاستيراد  —  Starting import...")

        imported, skipped = import_students(
            source_path=self._source_path,
            source_table=self._source_table,
            mapping=mapping,
            default_dept_id=dept_id,
            default_nationality_id=nat_id,
            log_callback=self._log_message,
        )

        self._log_message(
            f"\n{'='*40}\n"
            f"✅  تم استيراد: {imported} طالب\n"
            f"⚠️  تم تخطي:   {skipped} سجل\n"
            f"{'='*40}"
        )

    def _log_message(self, message: str) -> None:
        """Append a message to the log textbox."""
        self._log.configure(state="normal")
        self._log.insert("end", message + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")
        self.update_idletasks()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app = ImportToolWindow()
    app.mainloop()
