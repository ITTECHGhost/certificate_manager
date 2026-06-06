import mysql.connector
from config import DBConfig

conn = mysql.connector.connect(
    host=DBConfig.DB_HOST,
    user=DBConfig.DB_USER,
    password=DBConfig.DB_PASSWORD,
    database=DBConfig.DB_NAME
)
cursor = conn.cursor(dictionary=True)
cursor.execute("DESCRIBE academic_periods")
rows = cursor.fetchall()
with open("scratch/academic_periods_desc.txt", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(str(r) + "\n")
conn.close()
