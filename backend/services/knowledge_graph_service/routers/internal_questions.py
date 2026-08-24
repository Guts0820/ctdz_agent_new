import hashlib
import re
import unicodedata

from fastapi import APIRouter

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.embedding import embed_questions
from backend.services.knowledge_graph_service.models import (
    Question,
    StandardAnswerUpsertRequest,
    StandardAnswerUpsertResponse,
)


router = APIRouter(prefix="/internal/api", tags=["internal-questions"])


def normalize_question_text(text: str) -> str:
    """Create a stable canonical form for OCR punctuation/spacing variants."""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized, flags=re.UNICODE)


def question_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_question_text(text).encode("utf-8")).hexdigest()


@router.post("/questions/standard-answer", response_model=StandardAnswerUpsertResponse)
def upsert_standard_answers(request: StandardAnswerUpsertRequest) -> StandardAnswerUpsertResponse:
    base_items = [
        {
            "id": f"TQ{question_fingerprint(item.text)[:12].upper()}",
            "text": item.text.strip(),
            "fingerprint": question_fingerprint(item.text),
            "explanation": item.explanation.strip(),
            "answer": item.answer.strip(),
            "request_id": item.request_id,
            "grade": item.grade,
            "semester": item.semester,
            "difficulty": item.difficulty,
            "answer_source": item.answer_source,
            "created_by": item.created_by,
            "updated_by": item.updated_by,
            "llm_model": item.llm_model,
            "llm_solved_at": item.llm_solved_at,
            "llm_call_count": item.llm_call_count,
            "status": item.status,
            "standard_solution_status": item.standard_solution_status,
        }
        for item in request.items
    ]
    embeddings = embed_questions(base_items)
    items = [
        {**item, "embedding": embedding}
        for item, embedding in zip(base_items, embeddings)
    ]
    result = neo4j_conn.query(
        """
        UNWIND $items AS item
        MERGE (q:Question {fingerprint: item.fingerprint})
        ON CREATE SET q.id = item.id,
                      q.created_at = datetime(),
                      q.created_by = item.created_by,
                      q.created_request_id = item.request_id,
                      q.llm_call_count = coalesce(item.llm_call_count, 0)
        SET q.answer = item.answer,
            q.answer_steps = item.explanation,
            q.explanation = item.explanation,
            q.text = coalesce(q.text, item.text),
            q.embedding = item.embedding,
            q.grade = coalesce(item.grade, q.grade),
            q.semester = coalesce(item.semester, q.semester),
            q.difficulty = coalesce(item.difficulty, q.difficulty),
            q.source = 'teacher_upload',
            q.import_batch = 'teacher-standard-answer-v1',
            q.status = 'ready',
            q.standard_solution_status = 'ready',
            q.answer_source = coalesce(item.answer_source, q.answer_source),
            q.updated_by = coalesce(item.updated_by, q.updated_by),
            q.llm_model = coalesce(item.llm_model, q.llm_model),
            q.llm_solved_at = coalesce(item.llm_solved_at, q.llm_solved_at),
            q.llm_call_count = CASE
                WHEN item.llm_call_count IS NULL OR coalesce(q.llm_call_count, 0) >= item.llm_call_count
                THEN coalesce(q.llm_call_count, 0)
                ELSE item.llm_call_count
            END,
            q.last_request_id = item.request_id,
            q.updated_at = datetime()
        RETURN item.request_id AS request_id,
               q.created_request_id = item.request_id AS created,
               q
        """,
        {"items": items},
    )
    questions = [Question(**dict(row["q"])) for row in result]
    return StandardAnswerUpsertResponse(
        imported_count=len(questions),
        vectorized_count=sum(1 for embedding in embeddings if embedding),
        questions=questions,
        results=[
            {
                "request_id": row.get("request_id"),
                "question_id": str(dict(row["q"])["id"]),
                "result": "created" if row.get("created") else "updated",
            }
            for row in result
        ],
    )
