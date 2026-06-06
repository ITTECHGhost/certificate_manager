from db import get_connection
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SHOW DATABASES")
databases = [row[0] for row in cursor.fetchall()]
print("Databases in MySQL:")
for db in databases:
    print(f"- {db}")
conn.close()
