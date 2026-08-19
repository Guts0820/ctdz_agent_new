import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE = PROJECT_ROOT / "database" / "sqlite" / "example_db.db"

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in cursor.fetchall()]
print("数据库中的表:")
for t in tables:
    print(f"  - {t}")
conn.close()
