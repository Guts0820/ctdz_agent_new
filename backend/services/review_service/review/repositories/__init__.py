import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from backend.shared.neo4j_connection import neo4j_conn
from backend.services.review_service.review.domain.enums import AnalysisStatus, Difficulty, ItemStatus, PlanMode, PlanStatus
from backend.services.review_service.review.integrations.neo4j_contracts import Neo4jKnowledgeGraphClient
from backend.services.review_service.review.schemas.priority import KnowledgeStateInput, PracticeEvidence, PriorityRunResponse
from backend.services.review_service.review.schemas.review import (
    PlanningScoreBreakdown,
    QuestionInternal,
    ReviewPlan,
    ReviewPlanItem,
)

REVIEW_DATABASE = "database/sqlite/example_db.db"


def _get_review_db():
    conn = sqlite3.connect(REVIEW_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@dataclass
class SessionRecord:
    id: str
    plan_id: str
    student_id: str
    status: PlanStatus
    current_position: int
    elapsed_seconds: int
    started_at: datetime
    resumed_at: datetime | None
    attempt_ids: list[str] = field(default_factory=list)


@dataclass
class AttemptRecord:
    id: str
    session_id: str
    question_id: str
    position: int
    is_correct: bool
    analysis_status: AnalysisStatus
    submitted_at: datetime
    selected_option: int = 0
    answer: str = ""
    correction_count: int = 0
    correction_is_correct: bool | None = None
    correction_selected_option: int | None = None
    correction_answer: str | None = None
    correction_at: datetime | None = None
    policy_version: str | None = None
    error_tags: list | None = None
    judge_method: str = "fallback"
    correction_error_tags: list | None = None
    correction_judge_method: str | None = None


DIFFICULTY_MAP = {
    1: Difficulty.BASIC,
    2: Difficulty.PRACTICE,
    3: Difficulty.ADVANCED,
    "basic": Difficulty.BASIC,
    "practice": Difficulty.PRACTICE,
    "advanced": Difficulty.ADVANCED,
}

ERROR_SEVERITY_BY_LEVEL1 = {
    "概念": 0.9,
    "审题": 0.6,
    "计算": 0.5,
    "粗心": 0.3,
}


class Neo4jRepository:
    def __init__(self) -> None:
        self.graph_client = Neo4jKnowledgeGraphClient()
        # priority_runs 保持内存字典（5分钟缓存性质，不需要持久化）
        self.priority_runs: dict[tuple[str, date], PriorityRunResponse] = {}
        self._questions_cache: list[QuestionInternal] | None = None
        self._questions_cache_time: datetime | None = None

    def now(self) -> datetime:
        return datetime.now()

    def save_mastery(self, result, state: KnowledgeStateInput, mastery_status: str) -> str:
        """Persist the Review model as the single SQLite mastery read model."""
        with _get_review_db() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(knowledge_mastery)")}
            migrations = {
                "priority": "ALTER TABLE knowledge_mastery ADD COLUMN priority FLOAT DEFAULT 0",
                "formula_version": "ALTER TABLE knowledge_mastery ADD COLUMN formula_version VARCHAR(50)",
                "mastery_components": "ALTER TABLE knowledge_mastery ADD COLUMN mastery_components TEXT",
                "priority_components": "ALTER TABLE knowledge_mastery ADD COLUMN priority_components TEXT",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    conn.execute(statement)
            row = conn.execute(
                "SELECT knowledge_mastery_id FROM knowledge_mastery WHERE student_id = ? AND knowledge_id = ?",
                (str(state.student_id), state.knowledge_point_id),
            ).fetchone()
            mastery_id = row["knowledge_mastery_id"] if row else self.new_id("KM")
            conn.execute(
                """INSERT INTO knowledge_mastery
                   (knowledge_mastery_id, student_id, knowledge_id, mastery_status, correct_count,
                    wrong_count, master_level, priority, formula_version, mastery_components,
                    priority_components, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(knowledge_mastery_id) DO UPDATE SET
                    mastery_status=excluded.mastery_status, correct_count=excluded.correct_count,
                    wrong_count=excluded.wrong_count, master_level=excluded.master_level,
                    priority=excluded.priority, formula_version=excluded.formula_version,
                    mastery_components=excluded.mastery_components,
                    priority_components=excluded.priority_components, updated_at=excluded.updated_at""",
                (
                    mastery_id, str(state.student_id), state.knowledge_point_id, mastery_status,
                    state.correct_count, state.wrong_count, result.mastery.mastery / 100,
                    result.priority, result.formula_version, result.mastery.model_dump_json(),
                    result.components.model_dump_json(), result.calculated_at.isoformat(),
                ),
            )
            conn.commit()
        return mastery_id

    def get_knowledge_states(self, student_id: str) -> list[KnowledgeStateInput]:
        """P0-3: 从 answer_history (SQLite) 读取真实答题数据 → 聚合为 KnowledgeStateInput。
        knowledge_id 映射：先查 SQLite question_knowledge_mapping，再查 Neo4j EXAMINES。
        都查不到则跳过该条记录。没有数据时降级到 Neo4j AnswerHistory 查询。"""
        states = self._get_states_from_answer_history(student_id)
        if states:
            return states

        # SQLite 没数据 → 降级 Neo4j（兼容旧链路）
        from backend.services.review_service.review.integrations.neo4j_contracts import Neo4jKnowledgeStateClient
        client = Neo4jKnowledgeStateClient()
        return client.get_states(student_id)

    def _get_states_from_answer_history(self, student_id: str) -> list[KnowledgeStateInput]:
        """从 SQLite answer_history 聚合知识状态。"""
        rows = self._query_answer_history(student_id)
        if not rows:
            return []

        # 按 knowledge_id 聚合
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            kid = row["knowledge_id"]
            if kid not in grouped:
                grouped[kid] = []
            grouped[kid].append(row)

        states = []
        for kid, records in grouped.items():
            records.sort(key=lambda r: r["submitted_at"] or "")
            is_correct_list = [r["is_correct"] for r in records]

            correct_count = sum(1 for v in is_correct_list if v)
            wrong_count = sum(1 for v in is_correct_list if not v)

            # 计算最近连续 streak
            correct_streak = 0
            wrong_streak = 0
            for v in reversed(is_correct_list):
                if v:
                    if wrong_streak > 0:
                        break
                    correct_streak += 1
                else:
                    if correct_streak > 0:
                        break
                    wrong_streak += 1

            evidence = [
                PracticeEvidence(
                    is_correct=record["is_correct"],
                    occurred_at=datetime.fromisoformat(record["submitted_at"]),
                    error_severity=record.get("error_severity"),
                )
                for record in records
                if record.get("submitted_at")
            ]
            states.append(KnowledgeStateInput(
                student_id=student_id,
                knowledge_point_id=kid,
                correct_count=correct_count,
                wrong_count=wrong_count,
                correct_streak=correct_streak,
                wrong_streak=wrong_streak,
                evidence=evidence,
                importance=50.0,
                state_version=1,
            ))

        return states

    def _query_answer_history(self, student_id: str) -> list[dict]:
        """读取主链作答、复习作答与订正记录，并补齐 knowledge_id。"""
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT ah.question_id, ah.is_correct, ah.submitted_at, ah.error_tags
                   FROM answer_history ah
                   WHERE ah.student_id = ?
                   ORDER BY ah.submitted_at""",
                (student_id,),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            try:
                cursor.execute(
                    """SELECT ra.question_id, ra.is_correct, ra.submitted_at, ra.error_tags
                       FROM review2_attempt ra
                       JOIN review2_session rs ON rs.id = ra.session_id
                       WHERE rs.student_id = ?
                       UNION ALL
                       SELECT ra.question_id, ra.correction_is_correct, ra.correction_at,
                              ra.correction_error_tags
                       FROM review2_attempt ra
                       JOIN review2_session rs ON rs.id = ra.session_id
                       WHERE rs.student_id = ? AND ra.correction_at IS NOT NULL""",
                    (student_id, student_id),
                )
                rows.extend(dict(row) for row in cursor.fetchall())
            except sqlite3.OperationalError:
                # 兼容尚未初始化 review2_ 表的旧数据库和最小化单元测试库。
                pass

        if not rows:
            return []

        # 收集所有 question_id，批量查 knowledge_id
        qids = list({r["question_id"] for r in rows if r["question_id"]})

        # 第一路：SQLite question_knowledge_mapping
        kid_map: dict[str, str] = {}
        if qids:
            with _get_review_db() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" for _ in qids)
                cursor.execute(
                    f"SELECT question_id, knowledge_id FROM question_knowledge_mapping WHERE question_id IN ({placeholders})",
                    qids,
                )
                for r in cursor.fetchall():
                    kid_map[r["question_id"]] = r["knowledge_id"]

        # 第二路：Neo4j EXAMINES（查 SQLite 没覆盖的）
        missing = [q for q in qids if q not in kid_map]
        if missing:
            try:
                import sys as _sys
                _sys.path.insert(0, "backend")
                from backend.shared.neo4j_connection import neo4j_conn as neo4j_client
                for qid in missing:
                    neo4j_result = neo4j_client.query(
                        "MATCH (q:Question {id: $qid})-[r:EXAMINES]->(kp:KnowledgePoint) "
                        "RETURN kp.id AS knowledge_id",
                        {"qid": qid},
                    )
                    if neo4j_result:
                        kid_map[qid] = neo4j_result[0]["knowledge_id"]
            except Exception as e:
                print(f"[P0-3] Neo4j knowledge lookup failed for {len(missing)} questions: {e}")

        # 组装结果
        result = []
        for row in rows:
            kid = kid_map.get(row["question_id"])
            if kid:
                error_severity = None
                if not bool(row["is_correct"]) and row.get("error_tags"):
                    try:
                        tags = json.loads(row["error_tags"])
                        severities = [ERROR_SEVERITY_BY_LEVEL1.get(tag.get("level1"), 0.5) for tag in tags if isinstance(tag, dict)]
                        error_severity = max(severities, default=0.5)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        error_severity = 0.5
                result.append({
                    "knowledge_id": kid,
                    "is_correct": bool(row["is_correct"]),
                    "submitted_at": row["submitted_at"],
                    "error_severity": error_severity,
                })

        return result

    def _get_fallback_states(self, student_id: str) -> list[KnowledgeStateInput]:
        """图谱查不到真实学生数据时的降级方案，返回示例知识状态数据。"""
        from backend.services.review_service.review.schemas.priority import KnowledgeStateInput
        return [
            KnowledgeStateInput(
                student_id=student_id,
                knowledge_point_id="K001",
                correct_count=5,
                wrong_count=2,
                correct_streak=3,
                wrong_streak=0,
                importance=60,
                state_version=1,
            ),
            KnowledgeStateInput(
                student_id=student_id,
                knowledge_point_id="K002",
                correct_count=3,
                wrong_count=4,
                correct_streak=0,
                wrong_streak=2,
                importance=70,
                state_version=1,
            ),
            KnowledgeStateInput(
                student_id=student_id,
                knowledge_point_id="K003",
                correct_count=8,
                wrong_count=1,
                correct_streak=5,
                wrong_streak=0,
                importance=50,
                state_version=1,
            ),
            KnowledgeStateInput(
                student_id=student_id,
                knowledge_point_id="K004",
                correct_count=2,
                wrong_count=6,
                correct_streak=0,
                wrong_streak=3,
                importance=80,
                state_version=1,
            ),
        ]

    # ==================== Plan 持久化 ====================

    def get_plan_by_id(self, plan_id: str) -> ReviewPlan | None:
        """按 plan_id 查询复习计划（联表加载 plan_item 列表）。"""
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review2_plan WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT * FROM review2_plan_item WHERE plan_id = ? ORDER BY position",
                (plan_id,),
            )
            item_rows = cursor.fetchall()
        return self._row_to_plan(row, item_rows)

    def get_plan(self, plan_id: str) -> ReviewPlan | None:
        """兼容别名，推荐调用 get_plan_by_id()。"""
        return self.get_plan_by_id(plan_id)

    def get_plan_for_date(self, student_id: str, business_date: date) -> ReviewPlan | None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM review2_plan WHERE student_id = ? AND business_date = ? ORDER BY created_at DESC LIMIT 1",
                (student_id, business_date.isoformat()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "SELECT * FROM review2_plan_item WHERE plan_id = ? ORDER BY position",
                (row["id"],),
            )
            item_rows = cursor.fetchall()
        return self._row_to_plan(row, item_rows)

    def save_plan(self, plan: ReviewPlan) -> None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO review2_plan
                   (id, student_id, business_date, mode, question_count, time_limit_minutes,
                    priority_run_id, status, planning_config_version, created_at, frozen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan.id,
                    plan.student_id,
                    plan.business_date.isoformat(),
                    str(plan.mode),
                    plan.question_count,
                    plan.time_limit_minutes,
                    plan.priority_run_id,
                    str(plan.status),
                    plan.planning_config_version,
                    plan.created_at.isoformat(),
                    plan.frozen_at.isoformat() if plan.frozen_at else None,
                ),
            )
            # 先删旧 items 再插新的（items 可能因 update_capacity 变化）
            cursor.execute("DELETE FROM review2_plan_item WHERE plan_id = ?", (plan.id,))
            for item in plan.items:
                cursor.execute(
                    """INSERT INTO review2_plan_item
                       (plan_id, position, question_id, status, knowledge_point_ids, planning_score)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        plan.id,
                        item.position,
                        item.question_id,
                        str(item.status),
                        json.dumps(item.knowledge_point_ids),
                        item.planning_score.model_dump_json(),
                    ),
                )
            conn.commit()

    def _row_to_plan(self, row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> ReviewPlan:
        items = []
        for ir in item_rows:
            items.append(ReviewPlanItem(
                position=ir["position"],
                question_id=ir["question_id"],
                knowledge_point_ids=json.loads(ir["knowledge_point_ids"]),
                status=ItemStatus(ir["status"]),
                planning_score=PlanningScoreBreakdown.model_validate_json(ir["planning_score"]),
            ))
        return ReviewPlan(
            id=row["id"],
            student_id=row["student_id"],
            business_date=date.fromisoformat(row["business_date"]),
            mode=PlanMode(row["mode"]),
            question_count=row["question_count"],
            time_limit_minutes=row["time_limit_minutes"],
            priority_run_id=row["priority_run_id"],
            status=PlanStatus(row["status"]),
            items=items,
            created_at=datetime.fromisoformat(row["created_at"]),
            frozen_at=datetime.fromisoformat(row["frozen_at"]) if row["frozen_at"] else None,
            planning_config_version=row["planning_config_version"],
        )

    # ==================== Session 持久化 ====================

    def get_session(self, session_id: str) -> SessionRecord | None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review2_session WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute("SELECT id FROM review2_attempt WHERE session_id = ? ORDER BY submitted_at", (session_id,))
            attempt_ids = [r["id"] for r in cursor.fetchall()]
        return self._row_to_session(row, attempt_ids)

    def get_session_by_plan(self, plan_id: str) -> SessionRecord | None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM review2_session WHERE plan_id = ? ORDER BY started_at DESC LIMIT 1",
                (plan_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute("SELECT id FROM review2_attempt WHERE session_id = ? ORDER BY submitted_at", (row["id"],))
            attempt_ids = [r["id"] for r in cursor.fetchall()]
        return self._row_to_session(row, attempt_ids)

    def save_session(self, session: SessionRecord) -> None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO review2_session
                   (id, plan_id, student_id, status, current_position, elapsed_seconds, started_at, resumed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.plan_id,
                    session.student_id,
                    str(session.status),
                    session.current_position,
                    session.elapsed_seconds,
                    session.started_at.isoformat(),
                    session.resumed_at.isoformat() if session.resumed_at else None,
                ),
            )
            conn.commit()

    def _row_to_session(self, row: sqlite3.Row, attempt_ids: list[str]) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            plan_id=row["plan_id"],
            student_id=row["student_id"],
            status=PlanStatus(row["status"]),
            current_position=row["current_position"],
            elapsed_seconds=row["elapsed_seconds"],
            started_at=datetime.fromisoformat(row["started_at"]),
            resumed_at=datetime.fromisoformat(row["resumed_at"]) if row["resumed_at"] else None,
            attempt_ids=attempt_ids,
        )

    # ==================== Attempt 持久化 ====================

    def get_attempt(self, attempt_id: str) -> AttemptRecord | None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review2_attempt WHERE id = ?", (attempt_id,))
            row = cursor.fetchone()
        return self._row_to_attempt(row) if row else None

    def save_attempt(self, attempt: AttemptRecord) -> None:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO review2_attempt
                   (id, session_id, question_id, position, selected_option, student_answer,
                    is_correct, analysis_status, submitted_at, correction_count,
                    correction_is_correct, correction_selected_option, correction_answer,
                    correction_at, policy_version, error_tags, judge_method,
                    correction_error_tags, correction_judge_method)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attempt.id,
                    attempt.session_id,
                    attempt.question_id,
                    attempt.position,
                    attempt.selected_option,
                    attempt.answer,
                    int(attempt.is_correct),
                    str(attempt.analysis_status),
                    attempt.submitted_at.isoformat(),
                    attempt.correction_count,
                    int(attempt.correction_is_correct) if attempt.correction_is_correct is not None else None,
                    attempt.correction_selected_option,
                    attempt.correction_answer,
                    attempt.correction_at.isoformat() if attempt.correction_at else None,
                    attempt.policy_version,
                    json.dumps(attempt.error_tags, ensure_ascii=False) if attempt.error_tags else None,
                    attempt.judge_method,
                    json.dumps(attempt.correction_error_tags, ensure_ascii=False) if attempt.correction_error_tags else None,
                    attempt.correction_judge_method,
                ),
            )
            conn.commit()

    def get_attempts_for_session(self, session_id: str) -> list[AttemptRecord]:
        with _get_review_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM review2_attempt WHERE session_id = ? ORDER BY submitted_at",
                (session_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_attempt(row) for row in rows]

    def _row_to_attempt(self, row: sqlite3.Row) -> AttemptRecord:
        return AttemptRecord(
            id=row["id"],
            session_id=row["session_id"],
            question_id=row["question_id"],
            position=row["position"],
            is_correct=bool(row["is_correct"]),
            analysis_status=AnalysisStatus(row["analysis_status"]),
            submitted_at=datetime.fromisoformat(row["submitted_at"]),
            selected_option=row["selected_option"] or 0,
            answer=row["student_answer"] or "",
            correction_count=row["correction_count"] or 0,
            correction_is_correct=bool(row["correction_is_correct"]) if row["correction_is_correct"] is not None else None,
            correction_selected_option=row["correction_selected_option"],
            correction_answer=row["correction_answer"],
            correction_at=datetime.fromisoformat(row["correction_at"]) if row["correction_at"] else None,
            policy_version=row["policy_version"],
            error_tags=json.loads(row["error_tags"]) if row["error_tags"] else None,
            judge_method=row["judge_method"] or "fallback",
            correction_error_tags=json.loads(row["correction_error_tags"]) if row["correction_error_tags"] else None,
            correction_judge_method=row["correction_judge_method"],
        )

    # ==================== 其他方法 ====================

    def get_questions(self) -> list[QuestionInternal]:
        cache_ttl = 300
        now = self.now()
        if self._questions_cache and self._questions_cache_time:
            if (now - self._questions_cache_time).total_seconds() < cache_ttl:
                return self._questions_cache

        try:
            query = """
            MATCH (q:Question)-[r:EXAMINES]->(kp:KnowledgePoint)
            OPTIONAL MATCH (q)-[:HAS_IMAGE]->(img:Image)
            RETURN q.id AS id,
                   q.text AS prompt,
                   q.answer AS correct_answer,
                   q.answer_steps AS answer_steps,
                   q.options AS options,
                   q.difficulty AS difficulty,
                   kp.id AS knowledge_id,
                   kp.name AS knowledge_title,
                   r.weight AS weight,
                   img.image_url AS image_url
            ORDER BY q.id
            """
            results = neo4j_conn.query(query, {})
            question_map = {}

            for row in results:
                qid = row["id"]
                if qid not in question_map:
                    prompt = row.get("prompt", "") or ""
                    correct_answer = row.get("correct_answer", "") or ""
                    answer_steps_raw = row.get("answer_steps", "") or ""
                    raw_options = row.get("options", None)

                    # --- 题型判断 ---
                    # 1. 如果图谱里有 options 属性 → 选择题
                    if raw_options and isinstance(raw_options, list) and len(raw_options) > 0:
                        question_type = "choice"
                        options = [str(o) for o in raw_options]
                        correct_option = 0
                        if isinstance(correct_answer, int):
                            correct_option = correct_answer
                        elif isinstance(correct_answer, str) and correct_answer.strip().isdigit():
                            correct_option = int(correct_answer.strip())
                        answer = ""
                        answer_steps = []
                    # 2. 如果有 answer_steps → 开放题
                    elif answer_steps_raw and isinstance(answer_steps_raw, str) and answer_steps_raw.strip():
                        question_type = "open"
                        answer = str(correct_answer) if correct_answer else ""
                        answer_steps = [s.strip() for s in answer_steps_raw.split("\n") if s.strip()]
                        options = []
                        correct_option = 0
                    # 3. 兜底：有 answer 但没 answer_steps → 开放题（真实图谱绝大多数情况）
                    else:
                        question_type = "open"
                        answer = str(correct_answer) if correct_answer else ""
                        answer_steps = []
                        options = []
                        correct_option = 0

                    diff_raw = row.get("difficulty", 1)
                    if isinstance(diff_raw, (int, float)):
                        diff_num = int(diff_raw)
                    elif isinstance(diff_raw, str):
                        diff_num = DIFFICULTY_MAP.get(diff_raw.lower(), 1)
                        if isinstance(diff_num, str):
                            diff_num = {"basic": 1, "practice": 2, "advanced": 3}.get(diff_num, 1)
                        else:
                            diff_num = int(diff_raw) if diff_raw.isdigit() else 1
                    else:
                        diff_num = 1

                    difficulty = {1: Difficulty.BASIC, 2: Difficulty.PRACTICE, 3: Difficulty.ADVANCED}.get(diff_num, Difficulty.BASIC)

                    question_map[qid] = {
                        "id": qid,
                        "prompt": prompt,
                        "question_type": question_type,
                        "options": options,
                        "correct_option": correct_option,
                        "answer": answer,
                        "answer_steps": answer_steps,
                        "knowledge": [],
                        "difficulty": difficulty,
                        "estimated_minutes": 2,
                        "enabled": True,
                        "source_type": "neo4j",
                    }

                knowledge_id = row.get("knowledge_id")
                weight = row.get("weight", 1.0)
                if knowledge_id:
                    weight = float(weight) if weight else 1.0
                    question_map[qid]["knowledge"].append({
                        "knowledge_point_id": knowledge_id,
                        "weight": weight,
                    })

            questions = []
            for qid, qdata in question_map.items():
                if not qdata["knowledge"]:
                    qdata["knowledge"].append({
                        "knowledge_point_id": "unknown",
                        "weight": 1.0,
                    })
                try:
                    questions.append(QuestionInternal(**qdata))
                except Exception as e:
                    print(f"Error creating QuestionInternal for {qid}: {e}")

            self._questions_cache = questions
            self._questions_cache_time = now
            return questions

        except Exception as e:
            print(f"Error querying questions from Neo4j: {e}")
            return self._get_fallback_questions()

    def _get_fallback_questions(self) -> list[QuestionInternal]:
        fallback_data = [
            # 选择题示例
            {"id": "FB-001", "prompt": "计算 2.4 × 0.35，正确的结果是？", "question_type": "choice", "options": ["0.084", "0.84", "8.4", "84"], "correct_option": 1, "answer": "", "answer_steps": [], "knowledge": [{"knowledge_point_id": "K001", "weight": 1.0}], "difficulty": Difficulty.BASIC, "estimated_minutes": 2, "enabled": True, "source_type": "fallback"},
            # 开放题示例
            {"id": "FB-002", "prompt": "计算 2.4 × 0.35", "question_type": "open", "options": [], "correct_option": 0, "answer": "0.84", "answer_steps": ["2.4 × 0.35 = 0.84"], "knowledge": [{"knowledge_point_id": "K001", "weight": 1.0}], "difficulty": Difficulty.BASIC, "estimated_minutes": 2, "enabled": True, "source_type": "fallback"},
            # 开放题示例
            {"id": "FB-003", "prompt": "三角形底8cm、高5cm，求面积", "question_type": "open", "options": [], "correct_option": 0, "answer": "20", "answer_steps": ["三角形面积 = 底 × 高 ÷ 2", "8 × 5 ÷ 2 = 20", "面积是 20cm²"], "knowledge": [{"knowledge_point_id": "K003", "weight": 1.0}], "difficulty": Difficulty.PRACTICE, "estimated_minutes": 3, "enabled": True, "source_type": "fallback"},
            # 选择题示例
            {"id": "FB-004", "prompt": "7.2 ÷ 0.6 的商是多少？", "question_type": "choice", "options": ["1.2", "12", "120", "0.12"], "correct_option": 1, "answer": "", "answer_steps": [], "knowledge": [{"knowledge_point_id": "K002", "weight": 1.0}], "difficulty": Difficulty.BASIC, "estimated_minutes": 2, "enabled": True, "source_type": "fallback"},
            # 开放题示例
            {"id": "FB-005", "prompt": "1÷6 的商用循环小数表示", "question_type": "open", "options": [], "correct_option": 0, "answer": "0.1667", "answer_steps": ["1 ÷ 6 = 0.1666...", "6 作除数，结果为 0.1667（保留四位小数）"], "knowledge": [{"knowledge_point_id": "K004", "weight": 1.0}], "difficulty": Difficulty.PRACTICE, "estimated_minutes": 3, "enabled": True, "source_type": "fallback"},
        ]
        return [QuestionInternal(**data) for data in fallback_data]

    def get_question(self, question_id: str) -> QuestionInternal:
        questions = self.get_questions()
        for q in questions:
            if q.id == question_id:
                return q
        fallback = self._get_fallback_questions()
        if fallback:
            return fallback[0]
        raise LookupError(f"Question not found: {question_id}")

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:16]}"


repository = Neo4jRepository()
