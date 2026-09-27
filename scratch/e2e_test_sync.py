import os
import sys
from sync_engine import init_local_db, pull_mysql_to_sqlite, sync_offline_queue_to_mysql, _get_local_conn, get_queue_status
from db import get_connection

def main():
    print("Initializing Local DB...")
    init_local_db()

    conn = get_connection()
    try:
        print("Pulling MySQL to SQLite...")
        summary = pull_mysql_to_sqlite(conn)
        print("Pull Summary:", summary)
        
        # Test offline queue insertion
        print("Simulating Offline Certificate Generation...")
        local_conn = _get_local_conn()
        try:
            local_conn.execute(
                "INSERT INTO sync_queue (table_name, operation, temp_id, payload) "
                "VALUES ('issued_certificates', 'INSERT', -999, "
                "'{\"student_id\": 1, \"to_title\": \"Test Certificate\", \"template_type\": \"ARABIC\", \"issue_date\": \"2026-09-24\"}')"
            )
            local_conn.commit()
            print("Queue Status:", get_queue_status())
        finally:
            local_conn.close()

        print("Syncing Offline Queue to MySQL...")
        sync_result = sync_offline_queue_to_mysql(conn)
        print("Sync Result:", sync_result)

    finally:
        conn.close()

if __name__ == "__main__":
    main()
