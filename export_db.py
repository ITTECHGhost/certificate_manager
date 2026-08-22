import os
import sqlite3
import mysql.connector

MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678',
    'database': 'certificate_manager'
}

SQLITE_DB_PATH = 'local_cache.db'
OUTPUT_DIR = 'sql'

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

def export_mysql_schema():
    ensure_output_dir()
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    out_path = os.path.join(OUTPUT_DIR, 'schema.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write("-- MySQL Database Schema Export: certificate_manager\n")
        f.write("-- ========================================================\n\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")
        
        # 1. Tables
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = [list(row.values())[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            row = cursor.fetchone()
            create_stmt = row['Create Table']
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"-- Table structure for table `{table}`\n")
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            f.write(f"{create_stmt};\n\n")
            
        # 2. Views
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
        views = [list(row.values())[0] for row in cursor.fetchall()]
        
        for view in views:
            cursor.execute(f"SHOW CREATE VIEW `{view}`")
            row = cursor.fetchone()
            create_stmt = row.get('Create View') or list(row.values())[1]
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"-- View structure for `{view}`\n")
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"DROP VIEW IF EXISTS `{view}`;\n")
            f.write(f"{create_stmt};\n\n")
            
        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")
        
    cursor.close()
    conn.close()
    print(f"Exported MySQL schema to {out_path}")

def export_mysql_sps():
    ensure_output_dir()
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    out_path = os.path.join(OUTPUT_DIR, 'SP.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write("-- MySQL Stored Procedures Export: certificate_manager\n")
        f.write("-- ========================================================\n\n")
        
        cursor.execute("SHOW PROCEDURE STATUS WHERE Db = %s", (MYSQL_CONFIG['database'],))
        sps = [row['Name'] for row in cursor.fetchall()]
        
        for sp in sorted(sps):
            try:
                cursor.execute(f"SHOW CREATE PROCEDURE `{sp}`")
                row = cursor.fetchone()
                create_stmt = row.get('Create Procedure')
                if create_stmt:
                    f.write(f"-- --------------------------------------------------------\n")
                    f.write(f"-- Stored Procedure `{sp}`\n")
                    f.write(f"-- --------------------------------------------------------\n")
                    f.write("DELIMITER //\n")
                    f.write(f"DROP PROCEDURE IF EXISTS `{sp}` //\n")
                    f.write(f"{create_stmt} //\n")
                    f.write("DELIMITER ;\n\n")
            except Exception as e:
                print(f"Error exporting SP {sp}: {e}")
                
    cursor.close()
    conn.close()
    print(f"Exported MySQL Stored Procedures to {out_path}")

def export_sqlite_schema():
    ensure_output_dir()
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite DB '{SQLITE_DB_PATH}' not found.")
        return
        
    conn = sqlite3.connect(SQLITE_DB_PATH)
    out_path = os.path.join(OUTPUT_DIR, 'SQLite.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write(f"-- SQLite Database Schema & Dump: {SQLITE_DB_PATH}\n")
        f.write("-- ========================================================\n\n")
        for line in conn.iterdump():
            f.write(f"{line}\n")
    conn.close()
    print(f"Exported SQLite schema to {out_path}")

if __name__ == '__main__':
    export_mysql_schema()
    export_mysql_sps()
    export_sqlite_schema()
