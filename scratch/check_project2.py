import mysql.connector
from config import DBConfig

conn = mysql.connector.connect(
    host=DBConfig.DB_HOST,
    user=DBConfig.DB_USER,
    password=DBConfig.DB_PASSWORD,
    database="project2"
)
cursor = conn.cursor()
cursor.execute("SHOW TABLES")
tables = [row[0] for row in cursor.fetchall()]
print("Tables in project2 database:")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    count = cursor.fetchone()[0]
    print(f"- {t}: {count} rows")
conn.close()
