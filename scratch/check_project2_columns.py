import mysql.connector
from config import DBConfig

conn = mysql.connector.connect(
    host=DBConfig.DB_HOST,
    user=DBConfig.DB_USER,
    password=DBConfig.DB_PASSWORD,
    database="project2"
)
cursor = conn.cursor(dictionary=True)

with open("scratch/project2_columns_output.txt", "w", encoding="utf-8") as f:
    for table in ["subjects_students_140", "subjects_students_q"]:
        f.write(f"Table: {table}\n")
        cursor.execute(f"DESCRIBE {table}")
        for col in cursor.fetchall():
            f.write(f"  {col['Field']}: {col['Type']}\n")
        cursor.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cursor.fetchone()
        f.write(f"  Sample row: {repr(row)}\n")

conn.close()
