import sqlite3
import mysql.connector

def run():
    print("--- SQLite Course ---")
    conn = sqlite3.connect('local_cache.db')
    cur = conn.cursor()
    cur.execute("SELECT id, name_ar, stage_number FROM courses WHERE name_ar = 'التنقيب عن البيانات'")
    print(cur.fetchall())
    conn.close()

    print("--- MySQL Course ---")
    cfg = {'host':'127.0.0.1', 'user':'root', 'password':'', 'database':'certificate_manager'}
    try:
        mconn = mysql.connector.connect(**cfg)
        mcur = mconn.cursor(dictionary=True)
        mcur.execute("SELECT id, name_ar, stage_number FROM courses WHERE name_ar = 'التنقيب عن البيانات'")
        print(mcur.fetchall())
        mconn.close()
    except Exception as e:
        print('MySQL error:', e)

if __name__ == '__main__':
    run()
