import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from db import get_connection

def apply_sp():
    with open('sql/SP.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    with get_connection() as conn:
        cursor = conn.cursor()
        statements = sql.split('//')
        executed = 0
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            stmt_lines = [l for l in stmt.splitlines() if not l.strip().startswith('DELIMITER')]
            stmt_clean = '\n'.join(stmt_lines).strip()
            if not stmt_clean:
                continue
            try:
                cursor.execute(stmt_clean)
                executed += 1
            except Exception as e:
                print(f"Executing statement error: {e}")

        conn.commit()
        cursor.close()
    print(f"Successfully re-executed {executed} SP statements in MySQL database.")

if __name__ == '__main__':
    apply_sp()
