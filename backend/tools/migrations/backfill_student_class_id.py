"""回填 `students.class_id` 并把 `homework_batch.class_id` 统一成同一套口径。

授权（教师只能读本班学生）依赖"学生 → 班级"可判定，而库里三套班级写法并存：

- ``students.student_class``：``一(1)班``（低年级）、``三年级(1)班``（中高年级）
- ``teacher_class.class_name``：``一(1)班`` … ``三(1)班``，配 ``class_id`` = ``C001`` 这类
- ``homework_batch.class_id``：``1年级一班`` / ``C-001`` / ``一(1)班`` / ``三年级(1)班`` 混用

本脚本把三者统一到 ``teacher_class.class_id`` 口径：能判定就写回，判不定的**显式留在
NULL** 并写进 ``backend/logs/class_mismatch.csv`` —— 交给人工处理，绝不在授权时按猜测放行。

用法::

    python backend/tools/migrations/backfill_student_class_id.py             # 写回并导出 mismatch
    python backend/tools/migrations/backfill_student_class_id.py --dry-run   # 只看结果不落库
    python backend/tools/migrations/backfill_student_class_id.py --skip-batches
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.shared.config import DATABASE_PATH

DEFAULT_MISMATCH_PATH = PROJECT_ROOT / "backend" / "logs" / "class_mismatch.csv"

CHINESE_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
GRADE_RE = re.compile(r"([一二三四五六七八九]|\d+)\s*年级")
PAREN_CLASS_RE = re.compile(r"[（(]\s*(\d+)\s*[)）]")
GRADE_PAREN_RE = re.compile(r"([一二三四五六七八九]|\d+)\s*[（(]\s*(\d+)\s*[)）]")
CHINESE_CLASS_RE = re.compile(r"([一二三四五六七八九])\s*班")

STUDENTS_CLASS_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id)"


def _to_int(token: str) -> int | None:
    token = str(token).strip()
    if token.isdigit():
        return int(token)
    return CHINESE_DIGITS.get(token)


def parse_class_label(label: str | None, grade: str | None = None) -> tuple[int, int] | None:
    """把各种班级写法解析成 ``(年级号, 班号)``；解析不出来返回 None。

    ``一(1)班`` 这种低年级写法把年级写在了括号前，先按这个更明确的模式取一次。
    """
    text = str(label or "").strip()
    if not text:
        return None

    match = GRADE_PAREN_RE.search(text)
    if match:
        grade_number, class_number = _to_int(match.group(1)), int(match.group(2))
        if grade_number is not None:
            return (grade_number, class_number)

    grade_number = None
    for candidate in (grade, text):
        if not candidate:
            continue
        match = GRADE_RE.search(str(candidate))
        if match:
            grade_number = _to_int(match.group(1))
            break

    class_number = None
    match = PAREN_CLASS_RE.search(text)
    if match:
        class_number = int(match.group(1))
    else:
        match = CHINESE_CLASS_RE.search(text)
        if match:
            class_number = _to_int(match.group(1))

    if grade_number is None or class_number is None:
        return None
    return (grade_number, class_number)


def build_class_index(connection: sqlite3.Connection) -> dict[tuple[int, int], str]:
    """``teacher_class`` → ``{(年级号, 班号): class_id}``。"""
    index: dict[tuple[int, int], str] = {}
    rows = connection.execute("SELECT class_id, class_name, grade FROM teacher_class").fetchall()
    for class_id, class_name, grade in rows:
        key = parse_class_label(class_name, grade)
        if key and class_id:
            index[key] = str(class_id)
    return index


def resolve_class_id(
    label: str | None,
    grade: str | None,
    index: dict[tuple[int, int], str],
) -> str | None:
    """把一个班级写法解析成规范的 ``class_id``；判不定返回 None（不要猜）。"""
    text = str(label or "").strip()
    if not text:
        return None
    canonical = re.sub(r"[^0-9A-Za-z]", "", text).upper()
    if canonical and canonical in set(index.values()):
        return canonical
    key = parse_class_label(text, grade)
    return index.get(key) if key else None


def ensure_schema(connection: sqlite3.Connection) -> list[str]:
    """给已存在的库补列/补索引；返回实际执行的迁移语句。"""
    applied = []
    columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
    if "class_id" not in columns:
        connection.execute("ALTER TABLE students ADD COLUMN class_id VARCHAR(32)")
        applied.append("ALTER TABLE students ADD COLUMN class_id VARCHAR(32)")
    connection.execute(STUDENTS_CLASS_INDEX_SQL)
    applied.append(STUDENTS_CLASS_INDEX_SQL)
    connection.commit()
    return applied


def backfill(
    database_path: str | None = None,
    *,
    dry_run: bool = False,
    include_batches: bool = True,
    mismatch_path: Path | None = DEFAULT_MISMATCH_PATH,
) -> dict[str, Any]:
    """回填学生班级归属，并把作业批次的班级写法统一到 class_id 口径。"""
    path = database_path or DATABASE_PATH
    with sqlite3.connect(path) as connection:
        migrations = ensure_schema(connection)
        index = build_class_index(connection)

        mismatches: list[dict[str, Any]] = []
        assigned = 0
        students = connection.execute(
            "SELECT student_id, student_name, student_class, student_grade, class_id FROM students"
        ).fetchall()
        for student_id, student_name, student_class, student_grade, current in students:
            resolved = resolve_class_id(student_class, student_grade, index)
            if resolved is None:
                mismatches.append(
                    {
                        "kind": "student",
                        "identifier": student_id,
                        "label": student_class,
                        "grade": student_grade,
                        "resolved": "",
                        "detail": "无法关联 teacher_class，授权时必须拒绝而不是放行",
                    }
                )
                continue
            if resolved != current and not dry_run:
                connection.execute(
                    "UPDATE students SET class_id = ? WHERE student_id = ?",
                    (resolved, student_id),
                )
            assigned += 1

        batches_total = 0
        batches_updated = 0
        if include_batches:
            batches = connection.execute("SELECT batch_id, class_id FROM homework_batch").fetchall()
            for batch_id, class_id in batches:
                batches_total += 1
                resolved = resolve_class_id(class_id, None, index)
                if resolved is None:
                    mismatches.append(
                        {
                            "kind": "homework_batch",
                            "identifier": batch_id,
                            "label": class_id,
                            "grade": "",
                            "resolved": "",
                            "detail": "作业批次的班级写法无法判定",
                        }
                    )
                    continue
                if resolved != class_id:
                    if not dry_run:
                        connection.execute(
                            "UPDATE homework_batch SET class_id = ? WHERE batch_id = ?",
                            (resolved, batch_id),
                        )
                    batches_updated += 1

        if not dry_run:
            connection.commit()

    if mismatch_path is not None:
        write_mismatch_csv(mismatches, Path(mismatch_path))

    return {
        "students_total": len(students),
        "students_assigned": assigned,
        "students_unassigned": len(students) - assigned,
        "batches_total": batches_total,
        "batches_normalized": batches_updated,
        "migrations": migrations,
        "mismatches": mismatches,
        "dry_run": dry_run,
    }


def write_mismatch_csv(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "identifier", "label", "grade", "resolved", "detail"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="回填学生班级归属（授权前置条件）")
    parser.add_argument("--database", default="", help="SQLite 路径，默认取共享配置")
    parser.add_argument("--dry-run", action="store_true", help="只统计不落库")
    parser.add_argument("--skip-batches", action="store_true", help="不动 homework_batch")
    parser.add_argument("--mismatch-out", default=str(DEFAULT_MISMATCH_PATH), help="无法归属的记录输出路径")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    summary = backfill(
        args.database or None,
        dry_run=args.dry_run,
        include_batches=not args.skip_batches,
        mismatch_path=Path(args.mismatch_out),
    )

    print(f"库：{args.database or DATABASE_PATH}{'（dry-run，未落库）' if args.dry_run else ''}")
    for statement in summary["migrations"]:
        print(f"  迁移：{statement}")
    print(
        f"学生总数 {summary['students_total']} / 已归属 {summary['students_assigned']} / "
        f"未归属 {summary['students_unassigned']}"
    )
    if not args.skip_batches:
        print(
            f"作业批次 {summary['batches_total']} / 本次归一 {summary['batches_normalized']}"
        )
    if summary["students_unassigned"]:
        print(f"未归属明细：{args.mismatch_out}（{summary['students_unassigned']} 条）")
    else:
        print("所有学生都能判定班级归属")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
