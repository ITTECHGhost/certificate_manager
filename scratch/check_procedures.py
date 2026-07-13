import mysql.connector

def main():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor(dictionary=True)
    
    # Get all procedures
    cursor.execute("SHOW PROCEDURE STATUS WHERE Db = 'certificate_manager'")
    procedures = [row['Name'] for row in cursor.fetchall()]
    
    print("Checking stored procedures for 'postgraduation_no' or 'admission_year'...")
    for proc in procedures:
        cursor.execute(f"SHOW CREATE PROCEDURE {proc}")
        create_sql = cursor.fetchone()['Create Procedure']
        if 'postgraduation_no' in create_sql:
            print(f"Procedure '{proc}' references 'postgraduation_no'")
        if 'admission_year' in create_sql:
            # We want to know if it's in the students context
            print(f"Procedure '{proc}' references 'admission_year'")
            
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
