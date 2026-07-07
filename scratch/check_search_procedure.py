import mysql.connector
import sys

def check_procedure():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor(dictionary=True)
    
    # 1. Execute SearchStudentsBasic
    print("Executing SearchStudentsBasic('طالب')...")
    cursor.callproc("SearchStudentsBasic", ("طالب", 3))
    for rset in cursor.stored_results():
        rows = rset.fetchall()
        print("Results:")
        for r in rows:
            print(r)
            
    # 2. Let's see the CREATE PROCEDURE definition
    print("\nGetting definition of SearchStudentsBasic...")
    cursor.execute("SHOW CREATE PROCEDURE SearchStudentsBasic")
    row = cursor.fetchone()
    if row:
        print(row['Create Procedure'])
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_procedure()
