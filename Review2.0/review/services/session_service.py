from datetime import datetime

import requests

from review.domain.enums import AnalysisStatus, ItemStatus, PlanStatus
from review.repositories import AttemptRecord, Neo4jRepository, SessionRecord
from review.schemas.review import (
    AttemptResponse,
    CorrectionRequest,
    CorrectionResponse,
    QuestionForStudent,
    SessionStateResponse,
    StartSessionResponse,
    SubmitAttemptRequest,
)
from review.services.plan_service import PlanService

ANALYSIS_SERVICE_URL = "http://127.0.0.1:8081"
ERROR_ANALYSIS_AGENT_URL = "http://127.0.0.1:8082"

LEVEL1_SEVERITY = {
    "概念": 90,
    "审题": 60,
    "计算": 50,
    "粗心": 30,
}


def _calculate_error_severity(error_tags: list[dict] | None) -> float | None:
    if not error_tags:
        return None
    top_tag = max(error_tags, key=lambda t: t.get("confidence", 0))
    return float(LEVEL1_SEVERITY.get(top_tag.get("level1"), 50)) / 100.0


def _fuzzy_match(student_answer: str, correct_answer: str) -> bool:
    """模糊比对：数值答案容忍小数点差异，文本答案忽略空白大小写。"""
    s = student_answer.strip()
    c = correct_answer.strip()
    if s == c:
        return True
    # 数值比对：容忍 1% 误差或 2 位小数精度
    try:
        sv = float(s)
        cv = float(c)
        if cv == 0:
            return abs(sv) < 0.01
        # 先按两位小数比对，再按 5% 容差
        if round(sv, 2) == round(cv, 2):
            return True
        return abs(sv - cv) / max(abs(cv), 0.001) < 0.05  # 5% 容差
    except (ValueError, TypeError):
        pass
    # 文本比对：去空格，转小写
    return s.replace(" ", "").lower() == c.replace(" ", "").lower()


class SessionService:
    def __init__(self, repository: Neo4jRepository, plan_service: PlanService) -> None:
        self.repository = repository
        self.plan_service = plan_service

    def start(self, plan_id: str) -> StartSessionResponse:
        plan = self.plan_service.get(plan_id)
        # 原型阶段：每次都创建新会话
        if not plan.items:
            raise ValueError("计划中没有可用题目")
        plan.status = PlanStatus.IN_PROGRESS
        plan.frozen_at = self.repository.now()
        plan.items[0].status = ItemStatus.CURRENT
        session = SessionRecord(
            id=self.repository.new_id("session"),
            plan_id=plan.id,
            student_id=plan.student_id,
            status=PlanStatus.IN_PROGRESS,
            current_position=0,
            elapsed_seconds=0,
            started_at=self.repository.now(),
            resumed_at=self.repository.now(),
        )
        self.repository.save_plan(plan)
        self.repository.save_session(session)
        return StartSessionResponse(
            session_id=session.id,
            plan_id=plan.id,
            status=session.status,
            current_position=0,
            current_question=self._student_question(plan.items[0].question_id),
            elapsed_seconds=0,
        )

    def state(self, session_id: str) -> SessionStateResponse:
        session = self._get(session_id)
        plan = self.plan_service.get(session.plan_id)
        current = None
        if session.status != PlanStatus.COMPLETED:
            current = self._student_question(plan.items[session.current_position].question_id)
        all_attempts = self.repository.get_attempts_for_session(session.id)
        wrong_attempts = [a.id for a in all_attempts if not a.is_correct]
        return SessionStateResponse(
            session_id=session.id,
            plan_id=plan.id,
            status=session.status,
            current_position=session.current_position,
            total_questions=len(plan.items),
            elapsed_seconds=self._elapsed(session),
            current_question=current,
            wrong_attempt_ids=wrong_attempts,
        )

    def pause(self, session_id: str) -> SessionStateResponse:
        session = self._get(session_id)
        if session.status != PlanStatus.IN_PROGRESS:
            raise ValueError("只有进行中的Session可以暂停")
        session.elapsed_seconds = self._elapsed(session)
        session.resumed_at = None
        session.status = PlanStatus.PAUSED
        plan = self.plan_service.get(session.plan_id)
        plan.status = PlanStatus.PAUSED
        self.repository.save_session(session)
        self.repository.save_plan(plan)
        return self.state(session_id)

    def resume(self, session_id: str) -> SessionStateResponse:
        session = self._get(session_id)
        if session.status != PlanStatus.PAUSED:
            raise ValueError("只有暂停的Session可以恢复")
        session.status = PlanStatus.IN_PROGRESS
        session.resumed_at = self.repository.now()
        plan = self.plan_service.get(session.plan_id)
        plan.status = PlanStatus.IN_PROGRESS
        self.repository.save_session(session)
        self.repository.save_plan(plan)
        return self.state(session_id)

    def _judge_with_analysis_service(
        self,
        student_id: str,
        question,
        student_answer: str,
    ) -> tuple[bool, list[dict] | None, str]:
        """调用 Analysis Service 判题 + Error Analysis Agent 错因分析。

        返回 (is_correct, error_tags, judge_method)。
        任何异常都降级成简单字符串对比，judge_method 标记为 fallback。
        """
        standard_steps = "\n".join(question.answer_steps) if question.answer_steps else ""
        try:
            # 1. 调用 Analysis Service 判题
            resp = requests.post(
                f"{ANALYSIS_SERVICE_URL}/internal/api/v1/analysis/process",
                json={
                    "student_id": student_id,
                    "question_id": question.id,
                    "original_question": question.prompt,
                    "student_write": student_answer,
                    "standard_solve_steps": standard_steps,
                    "text_status": "normal",
                },
                timeout=30,
            )
            resp.raise_for_status()
            analysis = resp.json()
            judge_method = "ai"
            judge_result = analysis.get("judge_result", "unknown")
            is_correct = judge_result == "correct"
            # Analysis Service 不认识此题 → 降级为字符串对比
            if judge_result == "unknown" and question.answer:
                is_correct = _fuzzy_match(student_answer, question.answer)
                judge_method = "fallback"

            # 2. 答错时调用 Error Analysis Agent 获取错因标签
            error_tags = None
            if not is_correct:
                try:
                    ea_resp = requests.post(
                        f"{ERROR_ANALYSIS_AGENT_URL}/internal/api/v1/error-analysis/analyze",
                        json={
                            "student_id": student_id,
                            "question_id": question.id,
                            "original_question": question.prompt,
                            "student_write": student_answer,
                            "judge_result": judge_result,
                            "core_error_type": analysis.get("core_error_type", ""),
                            "step_feedback": analysis.get("step_feedback", ""),
                            "error_step_list": analysis.get("error_step_list", []),
                            "miss_step_list": analysis.get("miss_step_list", []),
                            "confidence": analysis.get("confidence"),
                        },
                        timeout=30,
                    )
                    ea_resp.raise_for_status()
                    ea_data = ea_resp.json()
                    error_tags = ea_data.get("error_tags") or None
                    if ea_data.get("low_confidence"):
                        print(f"[review] Error Analysis 返回低置信度结果 (total_confidence={ea_data.get('total_confidence', 'N/A')})，已降级使用")
                except Exception as ea_err:
                    print(f"[review] Error Analysis Agent 调用失败，降级（无错因标签）: {ea_err}")
                    error_tags = None

            return is_correct, error_tags, judge_method

        except Exception as a_err:
            print(f"[review] Analysis Service 调用失败，降级为字符串对比: {a_err}")
            is_correct = _fuzzy_match(student_answer, question.answer)
            return is_correct, None, "fallback"

    def submit(self, session_id: str, request: SubmitAttemptRequest) -> AttemptResponse:
        session = self._get(session_id)
        if session.status != PlanStatus.IN_PROGRESS:
            raise ValueError("Session当前不能提交答案")
        plan = self.plan_service.get(session.plan_id)
        item = plan.items[session.current_position]
        if request.question_id != item.question_id:
            raise ValueError("不能跳题或提交非当前题目")
        existing_attempts = self.repository.get_attempts_for_session(session.id)
        if any(a.position == item.position for a in existing_attempts):
            raise ValueError("当前题目已经提交，不能修改")
        question = self.repository.get_question(request.question_id)

        # --- 题型适配：选择题用选项索引比对，开放题接入 Analysis Service 判题 ---
        if question.question_type == "choice":
            if request.selected_option >= len(question.options):
                raise ValueError("选项超出范围")
            is_correct = request.selected_option == question.correct_option
            submitted_option = request.selected_option
            submitted_answer = ""
            error_tags = None
            judge_method = "local"
        else:
            submitted_answer = request.answer.strip()
            is_correct, error_tags, judge_method = self._judge_with_analysis_service(
                session.student_id, question, submitted_answer
            )
            submitted_option = 0

        now = self.repository.now()
        attempt = AttemptRecord(
            id=self.repository.new_id("attempt"),
            session_id=session.id,
            question_id=question.id,
            position=item.position,
            selected_option=submitted_option,
            answer=submitted_answer,
            is_correct=is_correct,
            analysis_status=AnalysisStatus.COMPLETED,
            submitted_at=now,
            error_tags=error_tags,
            judge_method=judge_method,
        )
        self.repository.save_attempt(attempt)
        item.status = ItemStatus.COMPLETED

        print("[DEBUG] 即将调用 _record_attempt_to_neo4j")
        self._record_attempt_to_neo4j(
            session.student_id, question.id, attempt.is_correct,
            request.selected_option, error_tags,
        )
        print("[DEBUG] _record_attempt_to_neo4j 调用完毕")

        completed = session.current_position == len(plan.items) - 1
        next_position = None
        if completed:
            session.elapsed_seconds = self._elapsed(session)
            session.resumed_at = None
            session.status = PlanStatus.COMPLETED
            plan.status = PlanStatus.COMPLETED
        else:
            session.current_position += 1
            next_position = session.current_position
            plan.items[next_position].status = ItemStatus.CURRENT

        self.repository.save_session(session)
        self.repository.save_plan(plan)

        return AttemptResponse(
            attempt_id=attempt.id,
            session_id=session.id,
            question_id=question.id,
            is_correct=attempt.is_correct,
            analysis_status=attempt.analysis_status,
            submitted_at=attempt.submitted_at,
            next_position=next_position,
            session_completed=completed,
            error_tags=error_tags,
            judge_method=judge_method,
        )

    def correct(self, attempt_id: str, request: CorrectionRequest) -> CorrectionResponse:
        attempt = self.repository.get_attempt(attempt_id)
        if not attempt:
            raise LookupError("答题记录不存在")
        session = self._get(attempt.session_id)
        if session.status != PlanStatus.COMPLETED:
            raise ValueError("正式复习完成后才能集中订正")
        if attempt.is_correct:
            raise ValueError("正确题目不需要订正")
        if attempt.correction_count >= 1:
            raise ValueError("每道错题只允许订正一次")
        question = self.repository.get_question(attempt.question_id)

        # --- 题型适配 ---
        if question.question_type == "choice":
            if request.selected_option >= len(question.options):
                raise ValueError("选项超出范围")
            attempt.correction_selected_option = request.selected_option
            attempt.correction_is_correct = request.selected_option == question.correct_option
            attempt.correction_answer = None
            correction_error_tags = None
            correction_judge_method = "local"
        else:
            # 订正也走 Analysis Service 判题 + 错因分析
            submitted_answer = request.answer.strip()
            attempt.correction_answer = submitted_answer
            is_correct, correction_error_tags, correction_judge_method = self._judge_with_analysis_service(
                session.student_id, question, submitted_answer
            )
            attempt.correction_is_correct = is_correct
            attempt.correction_selected_option = None
            attempt.correction_error_tags = correction_error_tags
            attempt.correction_judge_method = correction_judge_method

        attempt.correction_count = 1
        attempt.correction_at = self.repository.now()
        attempt.policy_version = "class-answer-policy-v1.0"
        self.repository.save_attempt(attempt)

        # 订正也更新Neo4j知识状态（订正也是一次真实作答证据）
        self._record_attempt_to_neo4j(
            session.student_id, question.id, bool(attempt.correction_is_correct),
            attempt.correction_selected_option or 0, correction_error_tags,
        )

        # 答案揭示由老师批次放行控制，不由学生订正对错决定
        batch_released = self._is_answer_released(question.id)
        return CorrectionResponse(
            attempt_id=attempt.id,
            correction_number=1,
            is_correct=bool(attempt.correction_is_correct),
            answer_revealed=batch_released,
            correct_option=question.correct_option if batch_released and question.question_type == "choice" else None,
            correct_answer=question.answer if batch_released and question.question_type == "open" else None,
            policy_version=attempt.policy_version or "",
            error_tags=correction_error_tags,
            judge_method=correction_judge_method,
            recorded_at=attempt.correction_at,
        )

    def _get(self, session_id: str) -> SessionRecord:
        session = self.repository.get_session(session_id)
        if not session:
            raise LookupError("Session不存在")
        return session

    def _student_question(self, question_id: str) -> QuestionForStudent:
        question = self.repository.get_question(question_id)
        return QuestionForStudent(
            id=question.id,
            prompt=question.prompt,
            question_type=question.question_type,
            options=question.options,
            answer=question.answer,
            answer_steps=question.answer_steps,
            knowledge_point_ids=[item.knowledge_point_id for item in question.knowledge],
            difficulty=question.difficulty,
            source_type=question.source_type,
        )

    def _elapsed(self, session: SessionRecord) -> int:
        if session.status != PlanStatus.IN_PROGRESS or session.resumed_at is None:
            return session.elapsed_seconds
        delta = self.repository.now() - session.resumed_at
        return session.elapsed_seconds + max(0, int(delta.total_seconds()))

    @staticmethod
    def _is_answer_released(question_id: str) -> bool:
        """查询题目所属作业批次是否已被老师放行。不在任何批次中 → 默认允许。"""
        import sqlite3
        try:
            conn = sqlite3.connect("backend/database/example_db.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT hb.release_status, hb.batch_id
                   FROM homework_batch_question hbq
                   JOIN homework_batch hb ON hbq.batch_id = hb.batch_id
                   WHERE hbq.question_id = ?
                   ORDER BY hb.created_at DESC LIMIT 1""",
                (question_id,),
            )
            row = cursor.fetchone()

            if not row:
                conn.close()
                return True  # 不在任何批次中，不限制

            status = row["release_status"]
            if status == "released":
                conn.close()
                return True
            if status == "partial":
                batch_id = row["batch_id"]
                cursor.execute(
                    "SELECT 1 FROM question_release_override WHERE batch_id = ? AND question_id = ?",
                    (batch_id, question_id),
                )
                has_override = cursor.fetchone() is not None
                conn.close()
                return has_override

            conn.close()
            return False  # locked
        except Exception:
            return True  # 查询失败不阻塞订正流程

    def _record_attempt_to_neo4j(
        self,
        student_id: str,
        question_id: str,
        is_correct: bool,
        selected_option: int,
        error_tags: list[dict] | None = None,
    ) -> None:
        print(f"[DEBUG] _record_attempt_to_neo4j 被调用了！student_id={student_id}, question_id={question_id}")
        import logging
        logger = logging.getLogger("review.session_service")
        try:
            from review.integrations.neo4j_contracts import Neo4jKnowledgeStateClient
            client = Neo4jKnowledgeStateClient()
            error_severity = _calculate_error_severity(error_tags)
            client.apply_attempt_evidence({
                "student_id": student_id,
                "question_id": question_id,
                "is_correct": is_correct,
                "selected_option": selected_option,
                "error_severity": error_severity,
            })
        except Exception as e:
            # 用 logger.exception 记录完整 traceback，不再静默 print
            # 不抛出：review 答题流程不应因 Neo4j 写入失败而中断
            # 但调用方可以通过日志监控发现这个问题
            logger.exception(
                "Failed to record attempt to Neo4j (student=%s, question=%s, is_correct=%s, severity=%s)",
                student_id, question_id, is_correct, _calculate_error_severity(error_tags),
            )