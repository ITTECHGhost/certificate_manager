import mysql.connector
from config import DBConfig

def main():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("DESCRIBE enrollments")
    print("enrollments table columns:")
    for col in cursor.fetchall():
        print(f"  {col['Field']}: {col['Type']}")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
