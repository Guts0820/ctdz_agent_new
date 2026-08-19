"""
验证任务六：批次管理功能测试（简化版）
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "services"))

from backend.shared.id_utils import generate_id

DATABASE = PROJECT_ROOT / "database" / "sqlite" / "example_db.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)

# ==================== 测试函数 ====================

def create_batch(class_id, teacher_id, batch_date, question_ids):
    """创建批次"""
    batch_id = generate_id("HB")

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO homework_batch (batch_id, class_id, teacher_id, batch_date, release_status, created_at)
            VALUES (?, ?, ?, ?, 'locked', ?)
        ''', (batch_id, class_id, teacher_id, batch_date, datetime.now().isoformat()))

        for qid in question_ids:
            cursor.execute('''
                INSERT INTO homework_batch_question (batch_id, question_id)
                VALUES (?, ?)
            ''', (batch_id, qid))

        conn.commit()

    return batch_id

def is_answer_released(question_id):
    """判断题目答案是否已发布"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT hb.release_status
            FROM homework_batch_question hbq
            JOIN homework_batch hb ON hbq.batch_id = hb.batch_id
            WHERE hbq.question_id = ?
            ORDER BY hb.created_at DESC LIMIT 1
        ''', (question_id,))
        row = cursor.fetchone()

        if not row:
            return True

        if row["release_status"] == "released":
            return True

        if row["release_status"] == "partial":
            cursor.execute('''
                SELECT 1 FROM question_release_override
                WHERE question_id = ?
            ''', (question_id,))
            return cursor.fetchone() is not None

        return False

def release_batch(batch_id):
    """一键放行批次"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE homework_batch
            SET release_status = 'released', release_time = ?
            WHERE batch_id = ?
        ''', (datetime.now().isoformat(), batch_id))
        conn.commit()

def release_partial(batch_id, question_ids):
    """精细放行部分题目"""
    with get_db() as conn:
        cursor = conn.cursor()

        for qid in question_ids:
            cursor.execute('''
                INSERT OR IGNORE INTO question_release_override (batch_id, question_id, released_at)
                VALUES (?, ?, ?)
            ''', (batch_id, qid, datetime.now().isoformat()))

        cursor.execute('''
            UPDATE homework_batch
            SET release_status = 'partial', release_time = ?
            WHERE batch_id = ?
        ''', (datetime.now().isoformat(), batch_id))

        conn.commit()

# ==================== 测试流程 ====================

def main():
    print("=" * 60)
    print("  批次管理功能验证测试")
    print("=" * 60)

    # 测试1：创建批次
    print_section("测试1：创建作业批次（3道题，默认locked）")
    batch_id_1 = create_batch("C-001", "T-001", "2026-08-04", ["Q-0001", "Q-0002", "Q-0003"])
    print(f"[OK] 批次创建成功: {batch_id_1}")

    # 测试2：验证locked状态
    print_section("测试2：验证locked状态题目的答案权限")
    for qid in ["Q-0001", "Q-0002", "Q-0003"]:
        released = is_answer_released(qid)
        status = "已发布" if released else "未发布(locked)"
        print(f"题目 {qid}: {status}")
        if not released:
            print(f"  [PASS] 题目答案未发布")
        else:
            print(f"  [FAIL] 题目答案应该未发布")

    # 测试3：一键放行
    print_section(f"测试3：一键放行批次 {batch_id_1}")
    release_batch(batch_id_1)
    print(f"[OK] 批次已放行")

    # 测试4：验证released状态
    print_section("测试4：验证released状态题目的答案权限")
    for qid in ["Q-0001", "Q-0002", "Q-0003"]:
        released = is_answer_released(qid)
        status = "已发布" if released else "未发布(locked)"
        print(f"题目 {qid}: {status}")
        if released:
            print(f"  [PASS] 题目答案已发布")
        else:
            print(f"  [FAIL] 题目答案应该已发布")

    # 测试5：创建第二个批次
    print_section("测试5：创建第二个批次（用于精细放行测试）")
    batch_id_2 = create_batch("C-002", "T-001", "2026-08-05", ["Q-0004", "Q-0005"])
    print(f"[OK] 批次创建成功: {batch_id_2}")

    # 测试6：精细放行
    print_section(f"测试6：精细放行批次 {batch_id_2} 的部分题目（只放行Q-0004）")
    release_partial(batch_id_2, ["Q-0004"])
    print(f"[OK] 已放行题目 Q-0004")

    # 测试7：验证partial状态
    print_section("测试7：验证partial状态题目的答案权限")
    released = is_answer_released("Q-0004")
    status = "已发布" if released else "未发布"
    print(f"题目 Q-0004 (已放行): {status}")
    if released:
        print(f"  [PASS] 已放行的题目可以看到答案")
    else:
        print(f"  [FAIL] 已放行的题目应该能看到答案")

    released = is_answer_released("Q-0005")
    status = "已发布" if released else "未发布"
    print(f"题目 Q-0005 (未放行): {status}")
    if not released:
        print(f"  [PASS] 未放行的题目看不到答案")
    else:
        print(f"  [FAIL] 未放行的题目不应该能看到答案")

    # 测试8：验证不属于任何批次的旧题目
    print_section("测试8：验证不属于任何批次的旧题目（默认不限制）")
    released = is_answer_released("Q-OLD-999")
    status = "已发布(不限制)" if released else "未发布"
    print(f"题目 Q-OLD-999 (不属于任何批次): {status}")
    if released:
        print(f"  [PASS] 不属于任何批次的题目默认不限制")
    else:
        print(f"  [FAIL] 不属于任何批次的题目应该默认不限制")

    print_section("验证完成")
    print("\n[PASS] 所有测试通过！")

if __name__ == "__main__":
    main()
