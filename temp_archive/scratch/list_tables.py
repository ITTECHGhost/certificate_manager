from db import get_connection
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SHOW TABLES")
tables = [row[0] for row in cursor.fetchall()]
print("Tables in certificate_manager database:")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    count = cursor.fetchone()[0]
    print(f"- {t}: {count} rows")
conn.close()
