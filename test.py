import sqlite3
try:
    conn=sqlite3.connect('certificate_manager.db')
    conn.execute("INSERT INTO personnel (name_ar, username, password, role) VALUES ('test2', 'test2', 'test', 'admin')")
    conn.commit()
    print("Success")
except Exception as e:
    print(e)
