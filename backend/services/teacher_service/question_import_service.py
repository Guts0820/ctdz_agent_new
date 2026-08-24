import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests
from fastapi import HTTPException

from backend.services.teacher_service.answer_comparison import AnswerComparison, compare_answers
from backend.services.teacher_service.database import ensure_question_import_tables, get_teacher_db
from backend.services.teacher_service.models import (
    QuestionImportConfirmRequest,
    QuestionImportConfirmResponse,
    QuestionImportConfirmResult,
    QuestionImportPreviewItem,
    QuestionImportPreviewResponse,
)
from backend.services.teacher_service.question_solver import solve_question_with_llm
from backend.services.teacher_service.standard_answer_service import (
    build_graph_items,
    recognize_standard_answer_image,
)
from backend.shared.config import HTTP_TIMEOUT_SECONDS, KNOWLEDGE_GRAPH_URL
from backend.shared.id_utils import generate_id
from backend.shared.llm_client import get_llm_model


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


def _stored_steps(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            return _steps(json.loads(value))
        except (TypeError, ValueError):
            pass
    return _steps(value)


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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


def upsert_confirmed_questions(items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Write confirmed canonical questions through the knowledge graph service."""
    try:
        response = requests.post(
            f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/internal/api/questions/standard-answer",
            json={"items": items},
            timeout=30,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"知识图谱服务不可用：{error}") from error
    try:
        payload = response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="知识图谱服务返回了无效 JSON。") from error
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=502,
            detail=detail or f"知识图谱服务返回 HTTP {response.status_code}",
        )
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="知识图谱服务返回了无效结果。")
    results = payload.get("results")
    if not isinstance(results, list):
        raise HTTPException(status_code=502, detail="知识图谱服务未返回题目写入结果。")
    mapped: dict[str, dict[str, str]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        request_id = str(result.get("request_id") or "")
        question_id = str(result.get("question_id") or "")
        result_status = str(result.get("result") or "")
        if request_id and question_id and result_status in {"created", "updated"}:
            mapped[request_id] = {"question_id": question_id, "result": result_status}
    return mapped


def sync_confirmed_questions_to_sqlite(
    graph_items: list[dict[str, Any]],
    graph_results: dict[str, dict[str, str]],
) -> None:
    """Mirror confirmed teacher questions into SQLite for submission and mastery joins."""
    rows = []
    for item in graph_items:
        result = graph_results.get(str(item["request_id"]))
        if result is None:
            continue
        rows.append((
            result["question_id"],
            item["text"],
            "教师导入题",
            item.get("difficulty") or "medium",
            f"{item['grade']}年级" if item.get("grade") else None,
            "教师导入",
            item.get("explanation") or "",
            item["answer"],
        ))
    if not rows:
        return
    with get_teacher_db() as connection:
        connection.executemany(
            """INSERT INTO question
               (question_id, question_description, question_type, difficulty, grade,
                textbook_version, standard_solve_steps, answer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(question_id) DO UPDATE SET
                   question_description=excluded.question_description,
                   question_type=excluded.question_type,
                   difficulty=excluded.difficulty,
                   grade=excluded.grade,
                   textbook_version=excluded.textbook_version,
                   standard_solve_steps=excluded.standard_solve_steps,
                   answer=excluded.answer""",
            rows,
        )
        connection.commit()


def _load_confirmed_response(import_id: str) -> QuestionImportConfirmResponse:
    with get_teacher_db() as connection:
        rows = connection.execute(
            "SELECT item_id, decision, confirmed_question_id, confirm_result "
            "FROM teacher_question_import_item WHERE import_id=? ORDER BY position",
            (import_id,),
        ).fetchall()
    return QuestionImportConfirmResponse(
        import_id=import_id,
        status="confirmed",
        items=[
            QuestionImportConfirmResult(
                item_id=row["item_id"],
                decision=row["decision"],
                question_id=row["confirmed_question_id"],
                result=row["confirm_result"],
            )
            for row in rows
        ],
    )


def _prepare_confirmation(
    import_id: str,
    session: Any,
    rows: list[Any],
    request: QuestionImportConfirmRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = {item.item_id: item for item in request.items}
    row_ids = {str(row["item_id"]) for row in rows}
    if set(decisions) != row_ids:
        raise HTTPException(status_code=422, detail="必须为预览中的每道题提交且只提交一个裁决。")

    graph_items: list[dict[str, Any]] = []
    prepared: list[dict[str, Any]] = []
    for row in rows:
        item_id = str(row["item_id"])
        decision = decisions[item_id]
        if decision.decision == "skip":
            prepared.append({"item_id": item_id, "decision": "skip", "result": "skipped"})
            continue
        if decision.decision == "existing":
            existing_question_id = str(row["existing_question_id"] or "")
            if not existing_question_id:
                raise HTTPException(status_code=422, detail=f"题目 {item_id} 未命中可复用的既有题目。")
            if decision.question_text is not None and decision.question_text.strip() != str(row["question_text"]).strip():
                raise HTTPException(status_code=422, detail=f"题目 {item_id} 已编辑，不能直接采用既有题目。")
            prepared.append({
                "item_id": item_id,
                "decision": "existing",
                "question_id": existing_question_id,
                "result": "existing",
            })
            continue

        question_text = (
            decision.question_text.strip()
            if decision.question_text is not None
            else str(row["question_text"]).strip()
        )
        if not question_text:
            raise HTTPException(status_code=422, detail=f"题目 {item_id} 的题干不能为空。")
        solve_steps = _stored_steps(row["llm_solve_steps"])
        if decision.decision == "llm":
            answer = str(row["llm_answer"] or "").strip()
            if not answer:
                raise HTTPException(status_code=422, detail=f"题目 {item_id} 没有可采用的 LLM 答案。")
            explanation = "\n".join(solve_steps)
            answer_source = "llm"
        else:
            answer = (
                decision.teacher_answer.strip()
                if decision.teacher_answer is not None
                else str(row["teacher_answer"]).strip()
            )
            if not answer:
                raise HTTPException(status_code=422, detail=f"题目 {item_id} 的教师答案不能为空。")
            teacher_explanation = (
                decision.teacher_explanation.strip()
                if decision.teacher_explanation is not None
                else str(row["teacher_explanation"] or "").strip()
            )
            explanation = teacher_explanation or "\n".join(solve_steps)
            answer_source = "teacher"

        request_id = hashlib.sha256(f"{import_id}\n{item_id}".encode("utf-8")).hexdigest()
        graph_items.append({
            "text": question_text,
            "answer": answer,
            "explanation": explanation,
            "request_id": request_id,
            "grade": int(session["grade"]),
            "semester": session["semester"],
            "difficulty": row["llm_difficulty"],
            "answer_source": answer_source,
            "created_by": request.teacher_id.strip(),
            "updated_by": request.teacher_id.strip(),
            "llm_model": row["llm_model"],
            "llm_solved_at": row["llm_solved_at"],
            "llm_call_count": 1 if row["solution_source"] == "llm" else 0,
            "status": "ready",
            "standard_solution_status": "ready",
        })
        prepared.append({
            "item_id": item_id,
            "decision": decision.decision,
            "request_id": request_id,
        })
    return graph_items, prepared


def confirm_question_import(
    import_id: str,
    request: QuestionImportConfirmRequest,
) -> QuestionImportConfirmResponse:
    teacher_id = request.teacher_id.strip()
    if not teacher_id:
        raise HTTPException(status_code=422, detail="teacher_id 不能为空")
    ensure_question_import_tables()
    with get_teacher_db() as connection:
        session = connection.execute(
            "SELECT * FROM teacher_question_import WHERE import_id=?", (import_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(status_code=404, detail="题目录入预览不存在")
        if str(session["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=403, detail="无权确认其他教师的题目录入会话。")
        if session["status"] == "confirmed":
            return _load_confirmed_response(import_id)
        if _datetime(session["expires_at"]) <= _now():
            connection.execute(
                "UPDATE teacher_question_import SET status='expired' WHERE import_id=?",
                (import_id,),
            )
            connection.commit()
            raise HTTPException(status_code=410, detail="题目录入预览已过期，请重新上传。")
        if session["status"] != "review_required":
            raise HTTPException(status_code=409, detail=f"当前会话状态不可确认：{session['status']}")
        rows = connection.execute(
            "SELECT * FROM teacher_question_import_item WHERE import_id=? ORDER BY position",
            (import_id,),
        ).fetchall()
        graph_items, prepared = _prepare_confirmation(import_id, session, rows, request)
        updated = connection.execute(
            "UPDATE teacher_question_import SET status='confirming' "
            "WHERE import_id=? AND status='review_required'",
            (import_id,),
        )
        if updated.rowcount != 1:
            connection.rollback()
            raise HTTPException(status_code=409, detail="题目录入会话正在确认，请勿重复提交。")
        connection.commit()

    try:
        graph_results = upsert_confirmed_questions(graph_items) if graph_items else {}
        for item in prepared:
            request_id = item.get("request_id")
            if request_id:
                result = graph_results.get(request_id)
                if result is None:
                    raise HTTPException(status_code=502, detail="知识图谱服务缺少题目写入结果。")
                item.update(result)
        sync_confirmed_questions_to_sqlite(graph_items, graph_results)
    except Exception:
        with get_teacher_db() as connection:
            connection.execute(
                "UPDATE teacher_question_import SET status='review_required' "
                "WHERE import_id=? AND status='confirming'",
                (import_id,),
            )
            connection.commit()
        raise

    confirmed_at = _now().isoformat()
    with get_teacher_db() as connection:
        for item in prepared:
            connection.execute(
                "UPDATE teacher_question_import_item SET decision=?, confirmed_question_id=?, confirm_result=? "
                "WHERE import_id=? AND item_id=?",
                (
                    item["decision"],
                    item.get("question_id"),
                    item["result"],
                    import_id,
                    item["item_id"],
                ),
            )
        connection.execute(
            "UPDATE teacher_question_import SET status='confirmed', confirmed_at=? "
            "WHERE import_id=? AND status='confirming'",
            (confirmed_at, import_id),
        )
        connection.commit()
    return _load_confirmed_response(import_id)


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
                llm_model = get_llm_model() if solution_source == "llm" else None
                llm_solved_at = _now().isoformat() if solution_source == "llm" else None
            except Exception:
                llm_answer = None
                solve_steps = []
                difficulty = None
                solution_source = "none"
                existing_question_id = None
                comparison_status = "llm_failed"
                comparison_reason = "LLM 独立解题失败，请教师人工确认"
                comparison_confidence = 0.0
                llm_model = None
                llm_solved_at = None
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
                llm_model,
                llm_solved_at,
                now,
            ))
        with get_teacher_db() as connection:
            connection.executemany(
                "INSERT INTO teacher_question_import_item "
                "(item_id, import_id, position, question_text, teacher_answer, teacher_explanation, "
                "llm_answer, llm_solve_steps, llm_difficulty, solution_source, comparison_status, "
                "comparison_reason, comparison_confidence, existing_question_id, llm_model, llm_solved_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
