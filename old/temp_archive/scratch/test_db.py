import mysql.connector
from config import DBConfig
from data.repositories import StudentRepository

try:
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    count = cursor.fetchone()[0]
    print(f"Connection successful! Total students in database: {count}")
    
    # Let's see some students
    cursor.execute("SELECT id, full_name_ar, full_name_en FROM students LIMIT 5")
    rows = cursor.fetchall()
    print("Sample students:")
    for r in rows:
        print(r)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
