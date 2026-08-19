import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE = PROJECT_ROOT / "database" / "sqlite" / "example_db.db"

# 查看 answer_history 中可用的错题数据。
conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# 错题记录（judge_result != correct）
c.execute("SELECT student_id, question_id, student_ocr_answer, judge_result, core_error_type, submitted_at FROM answer_history WHERE is_correct = 0 ORDER BY submitted_at DESC LIMIT 10")
rows = c.fetchall()

if rows:
    print(f"{len(rows)} 条错题记录:")
    for r in rows:
        print(f"  student={r['student_id']} q={r['question_id']} answer={r['student_ocr_answer']} type={r['core_error_type']} time={r['submitted_at']}")
else:
    c.execute("SELECT COUNT(*) FROM answer_history")
    total = c.fetchone()[0]
    print(f"answer_history 共 {total} 条，但 is_correct=0 的没有。")
    c.execute("SELECT is_correct, COUNT(*) FROM answer_history GROUP BY is_correct")
    for r in c.fetchall():
        print(f"  is_correct={r['is_correct']}: {r[1]} 条")

conn.close()
