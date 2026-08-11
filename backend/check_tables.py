import sqlite3

conn = sqlite3.connect('backend/database/example_db.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in cursor.fetchall()]
print("数据库中的表:")
for t in tables:
    print(f"  - {t}")
conn.close()