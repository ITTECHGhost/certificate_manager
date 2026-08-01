# =============================================================================
# get_db_schema.py — Database Schema & Stored Procedure Inspector
# =============================================================================
"""
Utility script to fetch, format, and display the MySQL (or SQLite fallback)
database schema and all Stored Procedures / Functions.

Usage:
    python get_db_schema.py                      # Inspect & display schema + SPs
    python get_db_schema.py --save               # Save report to db_schema_report.md
    python get_db_schema.py --table students     # Inspect specific table
    python get_db_schema.py --sp AuthenticateUser # Inspect specific stored procedure
    python get_db_schema.py --json               # Output schema as JSON file
    python get_db_schema.py --sqlite             # Inspect local SQLite cache schema
"""

import sys
import json
import argparse
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, cast

# Ensure UTF-8 output encoding for Windows terminal stdout and stderr if supported
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

# Try importing DB connection from project db.py
try:
    import db
    from config import DBConfig
    MYSQL_AVAILABLE = True
except Exception:
    MYSQL_AVAILABLE = False


def fetch_mysql_schema(host: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, db_name: Optional[str] = None) -> Dict[str, Any]:
    """Connects to MySQL and fetches complete table schemas, foreign keys, and stored procedures."""
    conn = None
    if MYSQL_AVAILABLE:
        try:
            conn = db.get_connection()
        except Exception:
            pass

    if not conn:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host or DBConfig.DB_HOST,
            user=user or DBConfig.DB_USER,
            password=password or DBConfig.DB_PASSWORD,
            database=db_name or DBConfig.DB_NAME,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )

    target_db = db_name or DBConfig.DB_NAME
    cursor = conn.cursor(dictionary=True)

    schema_info: Dict[str, Any] = {
        "database_type": "MySQL",
        "database_name": target_db,
        "host": host or DBConfig.DB_HOST,
        "tables": {},
        "stored_procedures": {},
        "functions": {}
    }

    # 1. Fetch Tables & Views
    cursor.execute("""
        SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS, TABLE_COLLATION, TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME
    """, (target_db,))
    tables = cast(List[Dict[str, Any]], cursor.fetchall())

    for tbl in tables:
        tbl_name = tbl["TABLE_NAME"]
        schema_info["tables"][tbl_name] = {
            "type": tbl["TABLE_TYPE"],
            "engine": tbl["ENGINE"],
            "approx_rows": tbl["TABLE_ROWS"],
            "collation": tbl["TABLE_COLLATION"],
            "comment": tbl["TABLE_COMMENT"],
            "columns": [],
            "foreign_keys": []
        }

        # Fetch Columns for Table
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, 
                   COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (target_db, tbl_name))
        columns = cast(List[Dict[str, Any]], cursor.fetchall())
        for col in columns:
            schema_info["tables"][tbl_name]["columns"].append({
                "name": col["COLUMN_NAME"],
                "type": col["COLUMN_TYPE"],
                "nullable": col["IS_NULLABLE"],
                "key": col["COLUMN_KEY"],
                "default": col["COLUMN_DEFAULT"],
                "extra": col["EXTRA"],
                "comment": col["COLUMN_COMMENT"]
            })

        # Fetch Foreign Keys
        cursor.execute("""
            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (target_db, tbl_name))
        fks = cast(List[Dict[str, Any]], cursor.fetchall())
        for fk in fks:
            schema_info["tables"][tbl_name]["foreign_keys"].append({
                "column": fk["COLUMN_NAME"],
                "ref_table": fk["REFERENCED_TABLE_NAME"],
                "ref_column": fk["REFERENCED_COLUMN_NAME"],
                "constraint": fk["CONSTRAINT_NAME"]
            })

    # 2. Fetch Stored Procedures & Functions
    cursor.execute("""
        SELECT ROUTINE_NAME, ROUTINE_TYPE, DTD_IDENTIFIER, ROUTINE_COMMENT, CREATED, LAST_ALTERED
        FROM information_schema.ROUTINES
        WHERE ROUTINE_SCHEMA = %s
        ORDER BY ROUTINE_TYPE, ROUTINE_NAME
    """, (target_db,))
    routines = cast(List[Dict[str, Any]], cursor.fetchall())

    raw_cursor = conn.cursor()
    for rtn in routines:
        rtn_name = rtn["ROUTINE_NAME"]
        rtn_type = rtn["ROUTINE_TYPE"]  # 'PROCEDURE' or 'FUNCTION'

        # Get parameters
        cursor.execute("""
            SELECT PARAMETER_NAME, PARAMETER_MODE, DATA_TYPE, DTD_IDENTIFIER
            FROM information_schema.PARAMETERS
            WHERE SPECIFIC_SCHEMA = %s AND SPECIFIC_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (target_db, rtn_name))
        params = cast(List[Dict[str, Any]], cursor.fetchall())

        param_list = []
        for p in params:
            if p["PARAMETER_NAME"]:
                param_list.append({
                    "name": p["PARAMETER_NAME"],
                    "mode": p["PARAMETER_MODE"] or "IN",
                    "type": p["DTD_IDENTIFIER"] or p["DATA_TYPE"]
                })

        # Fetch full SQL definition via SHOW CREATE PROCEDURE / FUNCTION
        create_sql = ""
        try:
            raw_cursor.execute(f"SHOW CREATE {rtn_type} `{rtn_name}`")
            create_row = raw_cursor.fetchone()
            if create_row:
                if isinstance(create_row, dict):
                    key = f"Create {rtn_type.capitalize()}"
                    create_sql = create_row.get(key) or create_row.get("Create Procedure") or create_row.get("Create Function") or ""
                elif isinstance(create_row, (tuple, list)):
                    if len(create_row) >= 3:
                        create_sql = create_row[2] or ""
                else:
                    row_any = cast(Any, create_row)
                    if len(row_any) >= 3:
                        create_sql = row_any[2] or ""
        except Exception as err:
            create_sql = f"-- Error fetching body: {err}"

        rtn_data = {
            "name": rtn_name,
            "type": rtn_type,
            "returns": rtn["DTD_IDENTIFIER"] if rtn_type == "FUNCTION" else None,
            "parameters": param_list,
            "comment": rtn["ROUTINE_COMMENT"],
            "definition": create_sql
        }

        if rtn_type == "PROCEDURE":
            schema_info["stored_procedures"][rtn_name] = rtn_data
        else:
            schema_info["functions"][rtn_name] = rtn_data

    raw_cursor.close()
    cursor.close()
    conn.close()

    return schema_info


def fetch_sqlite_schema(sqlite_path: str = "local_cache.db") -> Dict[str, Any]:
    """Inspects a local SQLite database file and extracts table schemas."""
    path = Path(sqlite_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database file not found: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    schema_info: Dict[str, Any] = {
        "database_type": "SQLite",
        "database_name": str(path.name),
        "host": "Local File System",
        "tables": {},
        "stored_procedures": {},
        "functions": {}
    }

    cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name")
    items = cursor.fetchall()

    for item in items:
        tbl_name = item["name"]
        
        # Row count
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl_name}`")
            count = cursor.fetchone()[0]
        except Exception:
            count = 0

        schema_info["tables"][tbl_name] = {
            "type": item["type"].upper(),
            "engine": "SQLite3",
            "approx_rows": count,
            "collation": "N/A",
            "comment": "",
            "create_sql": item["sql"],
            "columns": [],
            "foreign_keys": []
        }

        # Columns
        cursor.execute(f"PRAGMA table_info('{tbl_name}')")
        cols = cursor.fetchall()
        for c in cols:
            schema_info["tables"][tbl_name]["columns"].append({
                "name": c["name"],
                "type": c["type"] or "ANY",
                "nullable": "NO" if c["notnull"] else "YES",
                "key": "PRI" if c["pk"] else "",
                "default": c["dflt_value"],
                "extra": f"pk={c['pk']}" if c['pk'] else "",
                "comment": ""
            })

        # Foreign keys
        cursor.execute(f"PRAGMA foreign_key_list('{tbl_name}')")
        fks = cursor.fetchall()
        for fk in fks:
            schema_info["tables"][tbl_name]["foreign_keys"].append({
                "column": fk["from"],
                "ref_table": fk["table"],
                "ref_column": fk["to"],
                "constraint": f"fk_{fk['id']}"
            })

    conn.close()
    return schema_info


def display_schema(data: Dict[str, Any], filter_table: Optional[str] = None, filter_sp: Optional[str] = None, tables_only: bool = False, sps_only: bool = False):
    """Prints a formatted ASCII visual view of database tables and Stored Procedures to standard output."""
    db_type = data.get("database_type", "Database")
    db_name = data.get("database_name", "Unknown")
    tables = data.get("tables", {})
    sps = data.get("stored_procedures", {})
    funcs = data.get("functions", {})

    print("\n" + "=" * 80)
    print(f" DATABASE SCHEMA REPORT: {db_type.upper()} ({db_name})")
    print("=" * 80)
    print(f" Host / Location : {data.get('host', 'N/A')}")
    print(f" Total Tables    : {len(tables)}")
    print(f" Total Procedures: {len(sps)}")
    if funcs:
        print(f" Total Functions : {len(funcs)}")
    print("=" * 80 + "\n")

    # 1. DISPLAY TABLES
    if not sps_only:
        target_tables = {k: v for k, v in tables.items() if not filter_table or filter_table.lower() in k.lower()}
        if target_tables:
            print("+" + "-" * 78 + "+")
            print("| DATABASE TABLES                                                              |")
            print("+" + "-" * 78 + "+")

            for tbl_name, tbl_info in target_tables.items():
                row_str = f" (~{tbl_info['approx_rows']} rows)" if tbl_info.get("approx_rows") is not None else ""
                engine_str = f" [{tbl_info.get('engine', '')}]" if tbl_info.get('engine') else ""
                print(f"\n[TABLE]: {tbl_name}{engine_str}{row_str}")
                if tbl_info.get("comment"):
                    print(f"   Comment: {tbl_info['comment']}")
                
                # Print Column Header
                print("   +" + "-" * 30 + "+" + "-" * 18 + "+" + "-" * 8 + "+" + "-" * 6 + "+" + "-" * 10 + "+")
                print("   | " + "COLUMN NAME".ljust(28) + " | " + "TYPE".ljust(16) + " | " + "NULL".ljust(6) + " | " + "KEY".ljust(4) + " | " + "DEFAULT".ljust(8) + " |")
                print("   +" + "-" * 30 + "+" + "-" * 18 + "+" + "-" * 8 + "+" + "-" * 6 + "+" + "-" * 10 + "+")

                for col in tbl_info["columns"]:
                    c_name = str(col["name"])[:28].ljust(28)
                    c_type = str(col["type"])[:16].ljust(16)
                    c_null = str(col["nullable"]).ljust(6)
                    c_key  = str(col["key"] or "").ljust(4)
                    c_def  = str(col["default"] if col["default"] is not None else "NULL")[:8].ljust(8)
                    print(f"   | {c_name} | {c_type} | {c_null} | {c_key} | {c_def} |")
                
                print("   +" + "-" * 30 + "+" + "-" * 18 + "+" + "-" * 8 + "+" + "-" * 6 + "+" + "-" * 10 + "+")

                # Print Foreign Keys if any
                if tbl_info["foreign_keys"]:
                    print("   Foreign Keys:")
                    for fk in tbl_info["foreign_keys"]:
                        print(f"      * {fk['column']}  -->  {fk['ref_table']}({fk['ref_column']})")

    # 2. DISPLAY STORED PROCEDURES
    if not tables_only:
        target_sps = {k: v for k, v in sps.items() if not filter_sp or filter_sp.lower() in k.lower()}
        if target_sps:
            print("\n\n+" + "-" * 78 + "+")
            print("| STORED PROCEDURES                                                            |")
            print("+" + "-" * 78 + "+")

            for sp_name, sp_info in target_sps.items():
                print(f"\n[PROCEDURE]: {sp_name}")
                if sp_info.get("comment"):
                    print(f"   Comment: {sp_info['comment']}")

                params = sp_info.get("parameters", [])
                if params:
                    print("   Parameters:")
                    for p in params:
                        print(f"      * [{p['mode']}] {p['name']} : {p['type']}")
                else:
                    print("   Parameters: None (0 arguments)")

                definition = sp_info.get("definition", "").strip()
                if definition:
                    print("   Definition / Code:")
                    lines = definition.splitlines()
                    for line in lines[:25]:  # Preview first 25 lines
                        print(f"      | {line}")
                    if len(lines) > 25:
                        print(f"      | ... ({len(lines) - 25} more lines omitted in preview)")
                print("   " + "-" * 70)


def generate_markdown_report(data: Dict[str, Any]) -> str:
    """Generates a complete Markdown document summarizing schema and SPs."""
    db_type = data.get("database_type", "Database")
    db_name = data.get("database_name", "Unknown")
    tables = data.get("tables", {})
    sps = data.get("stored_procedures", {})

    md = []
    md.append(f"# {db_type} Database Schema & Stored Procedures Report")
    md.append(f"**Database**: `{db_name}`  ")
    md.append(f"**Host**: `{data.get('host', 'N/A')}`  ")
    md.append(f"**Total Tables**: {len(tables)} | **Total Stored Procedures**: {len(sps)}\n")
    md.append("---\n")

    # Tables section
    md.append("## 📋 Database Tables\n")
    for tbl_name, tbl in tables.items():
        row_str = f" (~{tbl['approx_rows']} rows)" if tbl.get("approx_rows") is not None else ""
        md.append(f"### Table: `{tbl_name}` {row_str}")
        if tbl.get("comment"):
            md.append(f"_{tbl['comment']}_\n")

        md.append("| Column Name | Type | Nullable | Key | Default | Extra |")
        md.append("|---|---|---|---|---|---|")
        for col in tbl["columns"]:
            c_def = str(col['default']) if col['default'] is not None else "NULL"
            md.append(f"| **{col['name']}** | `{col['type']}` | {col['nullable']} | {col['key']} | `{c_def}` | {col['extra']} |")
        
        if tbl["foreign_keys"]:
            md.append("\n**Foreign Keys**:")
            for fk in tbl["foreign_keys"]:
                md.append(f"- `{fk['column']}` -> `{fk['ref_table']}({fk['ref_column']})`")
        md.append("\n")

    # Stored Procedures section
    if sps:
        md.append("---\n")
        md.append("## ⚙️ Stored Procedures\n")
        for sp_name, sp in sps.items():
            md.append(f"### Procedure: `{sp_name}`")
            if sp.get("comment"):
                md.append(f"_{sp['comment']}_\n")

            if sp.get("parameters"):
                md.append("**Parameters**:")
                for p in sp["parameters"]:
                    md.append(f"- `{p['mode']}` **{p['name']}**: `{p['type']}`")
                md.append("")
            else:
                md.append("**Parameters**: None\n")

            if sp.get("definition"):
                md.append("```sql")
                md.append(sp["definition"])
                md.append("```\n")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Fetch and export MySQL / SQLite database schema and Stored Procedures to a Markdown report file.")
    parser.add_argument("--sqlite", action="store_true", help="Inspect local SQLite cache database (local_cache.db) instead of MySQL.")
    parser.add_argument("--sqlite-path", type=str, default="local_cache.db", help="Path to SQLite database file.")
    parser.add_argument("--output", "-o", type=str, default="db_schema_report.md", help="Output markdown file path (default: db_schema_report.md).")
    parser.add_argument("--print", "--console", dest="print_console", action="store_true", help="Print formatted ASCII schema view to console in addition to saving Markdown file.")
    parser.add_argument("--json", action="store_true", help="Export full schema metadata as JSON file (db_schema.json).")
    parser.add_argument("--table", type=str, help="Filter display for a specific table name.")
    parser.add_argument("--sp", type=str, help="Filter display for a specific stored procedure name.")
    parser.add_argument("--tables-only", action="store_true", help="Display only database tables.")
    parser.add_argument("--sps-only", action="store_true", help="Display only stored procedures.")

    args = parser.parse_args()

    schema_data = None
    if args.sqlite:
        print(f"Reading SQLite schema from {args.sqlite_path}...")
        try:
            schema_data = fetch_sqlite_schema(args.sqlite_path)
        except Exception as e:
            print(f"Error reading SQLite database: {e}")
            sys.exit(1)
    else:
        print("Connecting to MySQL database...")
        try:
            schema_data = fetch_mysql_schema()
        except Exception as err:
            print(f"MySQL connection error: {err}")
            print(f"Falling back to local SQLite cache database ({args.sqlite_path})...")
            try:
                schema_data = fetch_sqlite_schema(args.sqlite_path)
            except Exception as sq_err:
                print(f"Error reading SQLite database: {sq_err}")
                sys.exit(1)

    # 1. Always generate and save Markdown report by default
    md_content = generate_markdown_report(schema_data)
    out_path = Path(args.output)
    out_path.write_text(md_content, encoding="utf-8")
    print(f"\n[SUCCESS] Database schema report successfully written to Markdown file:\n  --> {out_path.resolve()}\n")

    # 2. Print formatted ASCII tables to console ONLY if explicitly requested via --print / --console
    if args.print_console:
        display_schema(
            schema_data,
            filter_table=args.table,
            filter_sp=args.sp,
            tables_only=args.tables_only,
            sps_only=args.sps_only
        )

    # 3. Export to JSON if requested
    if args.json:
        json_path = Path("db_schema.json")
        json_path.write_text(json.dumps(schema_data, indent=2, default=str), encoding="utf-8")
        print(f"Schema metadata exported to JSON: {json_path.resolve()}")


if __name__ == "__main__":
    main()
