import mysql.connector

def main():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor()
    
    print("--- students table columns ---")
    cursor.execute("DESCRIBE students")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- graduation_orders table columns ---")
    cursor.execute("DESCRIBE graduation_orders")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- InsertStudent Stored Procedure ---")
    try:
        cursor.execute("SHOW CREATE PROCEDURE InsertStudent")
        print(cursor.fetchone()[2])
    except Exception as e:
        print("Error fetching InsertStudent:", e)

    print("\n--- UpdateStudent Stored Procedure ---")
    try:
        cursor.execute("SHOW CREATE PROCEDURE UpdateStudent")
        print(cursor.fetchone()[2])
    except Exception as e:
        print("Error fetching UpdateStudent:", e)
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
