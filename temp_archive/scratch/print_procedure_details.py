import mysql.connector

def print_proc(cursor, name, out_f):
    try:
        cursor.execute(f"SHOW CREATE PROCEDURE {name}")
        row = cursor.fetchone()
        out_f.write(f"\n=========================================\nPROCEDURE: {name}\n=========================================\n\n")
        out_f.write(row['Create Procedure'])
        out_f.write("\n")
    except Exception as e:
        out_f.write(f"Error {name}: {e}\n")

def main():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345678",
        database="certificate_manager"
    )
    cursor = conn.cursor(dictionary=True)
    
    procs = [
        "InsertStudent", "UpdateStudent", "GetStudentDossierByID", 
        "GetFullCertificateData", "CountStudentsFiltered", 
        "GetStudentsPaginated", "SearchStudentsBasic"
    ]
    with open("scratch/procedure_details.txt", "w", encoding="utf-8") as out_f:
        for p in procs:
            print_proc(cursor, p, out_f)
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
