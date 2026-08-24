"""Real correction workflow for mistake cases created by the submission pipeline."""

from fastapi import HTTPException

from backend.api_gateway.models import MistakeCorrectionRequest, MistakeCorrectionResponse
from backend.api_gateway.services.analysis_client import analyze_submission
from backend.api_gateway.services.downstream import execute_downstream, require_fields
from backend.api_gateway.services.gateway_database import get_gateway_db
from backend.api_gateway.services.submission_service import _ensure_question_knowledge_mapping
from backend.api_gateway.services.state_client import update_state


def _teaching_level(master_level: float) -> tuple[str, str]:
    if master_level < 0.4:
        return "BASIC", "easy"
    if master_level <= 0.8:
        return "STANDARD", "medium"
    return "ADVANCED", "hard"


def _normalized_question(value: str) -> str:
    return "".join(value.split())


def _get_mistake_case(mistake_case_id: str):
    with get_gateway_db() as connection:
        return connection.execute(
            """SELECT mc.mistake_case_id, mc.student_id, mc.question_id, mc.current_status,
                      COALESCE(
                          (SELECT mck.knowledge_id FROM mistake_case_knowledge mck
                           WHERE mck.mistake_case_id = mc.mistake_case_id LIMIT 1),
                          (SELECT qkm.knowledge_id FROM question_knowledge_mapping qkm
                           WHERE qkm.question_id = mc.question_id LIMIT 1)
                      ) AS knowledge_id,
                      COALESCE(
                          (SELECT ah.ocr_question FROM answer_history ah
                           WHERE ah.mistake_case_id = mc.mistake_case_id
                           ORDER BY ah.submitted_at LIMIT 1),
                          q.question_description
                      ) AS stored_question,
                      COALESCE(
                          (SELECT tc.master_level FROM teaching_content tc
                           WHERE tc.mistake_case_id = mc.mistake_case_id
                           ORDER BY tc.created_at DESC LIMIT 1), 0.5
                      ) AS previous_master_level
               FROM mistake_case mc
               LEFT JOIN question q ON q.question_id = mc.question_id
               WHERE mc.mistake_case_id = ?""",
            (mistake_case_id,),
        ).fetchone()


def process_mistake_correction(
    mistake_case_id: str,
    request: MistakeCorrectionRequest,
) -> MistakeCorrectionResponse:
    mistake = _get_mistake_case(mistake_case_id)
    if not mistake:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    if mistake["current_status"] == "corrected":
        raise HTTPException(status_code=409, detail="该错题已经订正完成")

    original_question = request.original_question.strip()
    new_answer = request.new_answer.strip()
    if not original_question or not new_answer:
        raise HTTPException(status_code=422, detail="原题和新答案不能为空")
    stored_question = str(mistake["stored_question"] or "").strip()
    if stored_question and _normalized_question(original_question) != _normalized_question(stored_question):
        raise HTTPException(status_code=422, detail="原题与错题记录不一致")

    analysis = execute_downstream(
        "订正判题服务",
        lambda: analyze_submission({
            "student_id": mistake["student_id"],
            "question_id": mistake["question_id"],
            "original_question": original_question,
            "student_write": new_answer,
        }),
    )
    analysis = require_fields(
        "订正判题服务",
        analysis,
        {"answer_history_id", "judge_result", "confidence", "step_feedback"},
    )
    if analysis["judge_result"] not in {"correct", "wrong"}:
        raise HTTPException(status_code=502, detail="订正判题服务未返回明确判定")
    is_correct = analysis["judge_result"] == "correct"
    mistake_status = "corrected" if is_correct else "correcting"

    with get_gateway_db() as connection:
        previous_count = connection.execute(
            "SELECT COALESCE(MAX(submit_count), 0) FROM answer_history WHERE mistake_case_id = ?",
            (mistake_case_id,),
        ).fetchone()[0]
        submit_count = int(previous_count) + 1
        updated = connection.execute(
            """UPDATE answer_history
               SET mistake_case_id = ?, submit_type = ?, submit_count = ?
               WHERE answer_history_id = ?""",
            (mistake_case_id, "错题订正", submit_count, analysis["answer_history_id"]),
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=502, detail="订正记录未能关联到答题历史")
        connection.execute(
            "UPDATE mistake_case SET current_status = ? WHERE mistake_case_id = ?",
            (mistake_status, mistake_case_id),
        )
        connection.commit()

    state = None
    state_sync_status = "skipped"
    knowledge_id = analysis.get("knowledge_id") or mistake["knowledge_id"]
    if knowledge_id:
        try:
            if mistake["question_id"]:
                _ensure_question_knowledge_mapping(str(mistake["question_id"]), str(knowledge_id))
            state = execute_downstream(
                "学习状态服务",
                lambda: update_state(
                    mistake["student_id"],
                    knowledge_id,
                    is_correct,
                    analysis["confidence"],
                    analysis["answer_history_id"],
                    mistake_case_id,
                ),
            )
            state_sync_status = "updated"
        except HTTPException:
            # The correction record is authoritative and must remain usable even if state refresh is down.
            state_sync_status = "pending"

    master_level = float(state["master_level"]) if state else float(mistake["previous_master_level"] or 0.5)
    teaching_mode, teaching_difficulty = _teaching_level(master_level)
    return MistakeCorrectionResponse(
        mistake_case_id=mistake_case_id,
        answer_history_id=analysis["answer_history_id"],
        question_id=mistake["question_id"],
        original_question=original_question,
        new_answer=new_answer,
        judge_result=analysis["judge_result"],
        is_correct=is_correct,
        mistake_status=mistake_status,
        teaching_mode=teaching_mode,
        teaching_difficulty=teaching_difficulty,
        submit_type="错题订正",
        submit_count=submit_count,
        master_level=master_level,
        mastery=state.get("mastery") if state else None,
        priority=state.get("priority") if state else None,
        next_action=state.get("next_action") if state else None,
        state_sync_status=state_sync_status,
        step_feedback=analysis["step_feedback"],
    )
