# =============================================================================
# hash_existing_passwords.py — convert every plain-text password in MySQL to a hash
#
# Passwords are also converted one by one at each user's next login; this converts
# all remaining ones at once (including users who rarely log in), so no laptop keeps
# a readable password in its offline copy after the next sync.
#
# Run on the SERVER laptop: hash_existing_passwords.bat (asks before changing anything).
# Uses the MySQL login in config.py. Safe to run more than once.
# =============================================================================

import mysql.connector

from config import DBConfig
from password_hashing import hash_password, is_disabled, is_hashed


def main() -> None:
    conn = mysql.connector.connect(host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
                                   password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, password_hash FROM personnel ORDER BY id")
    rows = cur.fetchall()
    todo = [r for r in rows if not is_hashed(r["password_hash"]) and not is_disabled(r["password_hash"])]
    print(f"{len(rows)} accounts: {len(rows) - len(todo)} already hashed or disabled, {len(todo)} plain-text.")
    if not todo:
        print("Nothing to do.")
        return
    for r in todo:
        print(f"  - {r['id']}: {r['username']}")
    if input("Convert these passwords to hashes now? Type YES: ").strip() != "YES":
        print("Cancelled. Nothing was changed.")
        return
    for r in todo:
        cur.execute("UPDATE personnel SET password_hash = %s WHERE id = %s", (hash_password(r["password_hash"]), r["id"]))
    conn.commit()
    print(f"Done: {len(todo)} passwords converted. Users log in with the same passwords as before.")


if __name__ == "__main__":
    main()
