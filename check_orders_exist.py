
import sqlite3
conn = sqlite3.connect('certificate_manager.db')
target_orders = ['8682/13/3', '13038/13/3', '3/13/18427']
rows = conn.execute("SELECT order_number FROM graduation_orders").fetchall()
all_orders = [r[0] for r in rows]

for target in target_orders:
    if target in all_orders:
        print(f"Order {target} FOUND")
    else:
        print(f"Order {target} MISSING")
