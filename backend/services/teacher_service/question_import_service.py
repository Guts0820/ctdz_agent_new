import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests
from fastapi import HTTPException

from backend.services.teacher_service.answer_comparison import AnswerComparison, compare_answers
from backend.services.teacher_service.database import ensure_question_import_tables, get_teacher_db
from backend.services.teacher_service.models import QuestionImportPreviewItem, QuestionImportPreviewResponse
from backend.services.teacher_service.question_solver import solve_question_with_llm
from backend.services.teacher_service.standard_answer_service import (
    build_graph_items,
    recognize_standard_answer_image,
)
from backend.shared.config import HTTP_TIMEOUT_SECONDS, KNOWLEDGE_GRAPH_URL
from backend.shared.id_utils import generate_id


PREVIEW_TTL_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _request_key(image_bytes: bytes, teacher_id: str, grade: int, semester: str | None) -> tuple[str, str]:
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    key_material = f"{image_sha256}\n{teacher_id.strip()}\n{grade}\n{(semester or '').strip()}"
    return image_sha256, hashlib.sha256(key_material.encode("utf-8")).hexdigest()


def _difficulty(value: Any) -> str | None:
    if value in {"easy", "medium", "hard"}:
        return str(value)
    return {1: "easy", 2: "medium", 3: "hard"}.get(value)


def _steps(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def find_existing_question(question_text: str) -> dict[str, Any] | None:
    """Return an exact normalized canonical match; lookup failure is non-fatal for preview."""
    try:
        response = requests.get(
            f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/api/questions/candidates?text={quote(question_text)}&limit=1",
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            return None
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    candidates = payload.get("data", []) if isinstance(payload, dict) else []
    if not candidates or not isinstance(candidates[0], dict):
        return None
    candidate = candidates[0]
    if candidate.get("match_type") != "normalized_exact" or float(candidate.get("retrieval_score", 0)) < 0.999:
        return None
    if candidate.get("status", "ready") != "ready" or candidate.get("standard_solution_status", "ready") != "ready":
        return None
    return candidate


def _item_from_row(row: Any) -> QuestionImportPreviewItem:
    try:
        solve_steps = json.loads(row["llm_solve_steps"] or "[]")
    except (TypeError, ValueError):
        solve_steps = []
    return QuestionImportPreviewItem(
        item_id=row["item_id"],
        position=row["position"],
        question_text=row["question_text"],
        teacher_answer=row["teacher_answer"],
        teacher_explanation=row["teacher_explanation"] or "",
        llm_answer=row["llm_answer"],
        llm_solve_steps=solve_steps,
        difficulty=_difficulty(row["llm_difficulty"]),
        solution_source=row["solution_source"],
        comparison_status=row["comparison_status"],
        comparison_reason=row["comparison_reason"] or "",
        comparison_confidence=float(row["comparison_confidence"] or 0),
        existing_question_id=row["existing_question_id"],
    )


def _load_preview(import_id: str) -> QuestionImportPreviewResponse:
    with get_teacher_db() as connection:
        session = connection.execute(
            "SELECT * FROM teacher_question_import WHERE import_id = ?", (import_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="题目录入预览不存在")
        rows = connection.execute(
            "SELECT * FROM teacher_question_import_item WHERE import_id = ? ORDER BY position",
            (import_id,),
        ).fetchall()
    return QuestionImportPreviewResponse(
        import_id=session["import_id"],
        teacher_id=session["teacher_id"],
        grade=session["grade"],
        semester=session["semester"],
        status="review_required",
        ocr_confidence=session["ocr_confidence"],
        ocr_engine=session["ocr_engine"],
        items=[_item_from_row(row) for row in rows],
    )


def _begin_import(
    *, teacher_id: str, grade: int, semester: str | None, image_sha256: str, request_key: str
) -> tuple[str, bool]:
    now = _now()
    with get_teacher_db() as connection:
        existing = connection.execute(
            "SELECT import_id, status, expires_at FROM teacher_question_import WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        if existing is not None:
            expires_at = datetime.fromisoformat(existing["expires_at"])
            if existing["status"] == "review_required" and expires_at > now:
                return str(existing["import_id"]), True
            if existing["status"] == "processing" and expires_at > now:
                raise HTTPException(status_code=409, detail="相同图片正在处理中，请稍后重试")
            import_id = str(existing["import_id"])
            connection.execute("DELETE FROM teacher_question_import_item WHERE import_id = ?", (import_id,))
            connection.execute(
                "UPDATE teacher_question_import SET status='processing', error_message=NULL, created_at=?, expires_at=? "
                "WHERE import_id=?",
                (now.isoformat(), (now + timedelta(hours=PREVIEW_TTL_HOURS)).isoformat(), import_id),
            )
            connection.commit()
            return import_id, False

        import_id = generate_id("TQI")
        connection.execute(
            "INSERT INTO teacher_question_import "
            "(import_id, teacher_id, grade, semester, status, image_sha256, request_key, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, 'processing', ?, ?, ?, ?)",
            (
                import_id,
                teacher_id,
                grade,
                semester,
                image_sha256,
                request_key,
                now.isoformat(),
                (now + timedelta(hours=PREVIEW_TTL_HOURS)).isoformat(),
            ),
        )
        connection.commit()
    return import_id, False


def _mark_failed(import_id: str, error: Exception) -> None:
    with get_teacher_db() as connection:
        connection.execute(
            "UPDATE teacher_question_import SET status='failed', error_message=? WHERE import_id=?",
            (str(error)[:500], import_id),
        )
        connection.commit()


def _resolve_solution(question_text: str, grade: int, semester: str | None) -> tuple[dict, str, str | None]:
    existing = find_existing_question(question_text)
    if existing and str(existing.get("answer") or "").strip():
        return {
            "answer": str(existing["answer"]).strip(),
            "solve_steps": _steps(existing.get("answer_steps") or existing.get("explanation")),
            "difficulty": _difficulty(existing.get("difficulty")),
        }, "existing", str(existing.get("id") or "") or None
    return solve_question_with_llm(
        question_text=question_text,
        grade=grade,
        semester=semester,
    ), "llm", None


def create_question_import_preview(
    *,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    teacher_id: str,
    grade: int,
    semester: str | None,
) -> QuestionImportPreviewResponse:
    teacher_id = teacher_id.strip()
    if not teacher_id:
        raise HTTPException(status_code=422, detail="teacher_id 不能为空")
    if grade < 1 or grade > 6:
        raise HTTPException(status_code=422, detail="grade 必须在 1 到 6 之间")
    semester = semester.strip() if semester and semester.strip() else None

    ensure_question_import_tables()
    image_sha256, request_key = _request_key(image_bytes, teacher_id, grade, semester)
    import_id, reused = _begin_import(
        teacher_id=teacher_id,
        grade=grade,
        semester=semester,
        image_sha256=image_sha256,
        request_key=request_key,
    )
    if reused:
        return _load_preview(import_id)

    try:
        ocr_payload = recognize_standard_answer_image(image_bytes, filename, content_type)
        ocr_items = build_graph_items(ocr_payload)
        analysis_input = ocr_payload.get("analysis_input", ocr_payload)
        confidence = float(analysis_input.get("confidence", ocr_payload.get("confidence", 0)))
        engine = str(ocr_payload.get("engine") or analysis_input.get("engine") or "") or None
        now = _now().isoformat()
        rows = []
        for position, item in enumerate(ocr_items, start=1):
            item_id = generate_id("TQII")
            try:
                solution, solution_source, existing_question_id = _resolve_solution(
                    item["text"], grade, semester
                )
                llm_answer = str(solution.get("answer") or "").strip()
                if not llm_answer:
                    raise ValueError("解题结果缺少答案")
                solve_steps = _steps(solution.get("solve_steps"))
                difficulty = _difficulty(solution.get("difficulty"))
                comparison: AnswerComparison = compare_answers(item["answer"], llm_answer)
                comparison_status = comparison.status
                comparison_reason = comparison.reason
                comparison_confidence = comparison.confidence
            except Exception:
                llm_answer = None
                solve_steps = []
                difficulty = None
                solution_source = "none"
                existing_question_id = None
                comparison_status = "llm_failed"
                comparison_reason = "LLM 独立解题失败，请教师人工确认"
                comparison_confidence = 0.0
            rows.append((
                item_id,
                import_id,
                position,
                item["text"],
                item["answer"],
                item.get("explanation", ""),
                llm_answer,
                json.dumps(solve_steps, ensure_ascii=False),
                difficulty,
                solution_source,
                comparison_status,
                comparison_reason,
                comparison_confidence,
                existing_question_id,
                now,
            ))
        with get_teacher_db() as connection:
            connection.executemany(
                "INSERT INTO teacher_question_import_item "
                "(item_id, import_id, position, question_text, teacher_answer, teacher_explanation, "
                "llm_answer, llm_solve_steps, llm_difficulty, solution_source, comparison_status, "
                "comparison_reason, comparison_confidence, existing_question_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            connection.execute(
                "UPDATE teacher_question_import SET status='review_required', ocr_confidence=?, ocr_engine=? "
                "WHERE import_id=?",
                (confidence, engine, import_id),
            )
            connection.commit()
    except Exception as error:
        _mark_failed(import_id, error)
        raise
    return _load_preview(import_id)
