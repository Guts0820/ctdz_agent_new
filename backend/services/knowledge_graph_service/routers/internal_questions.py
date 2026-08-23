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
                      q.llm_call_count = 0
        SET q.answer = item.answer,
            q.answer_steps = item.explanation,
            q.explanation = item.explanation,
            q.text = coalesce(q.text, item.text),
            q.embedding = item.embedding,
            q.source = 'teacher_upload',
            q.import_batch = 'teacher-standard-answer-v1',
            q.status = 'ready',
            q.standard_solution_status = 'ready',
            q.last_request_id = item.request_id,
            q.updated_at = datetime()
        RETURN q
        """,
        {"items": items},
    )
    questions = [Question(**dict(row["q"])) for row in result]
    return StandardAnswerUpsertResponse(
        imported_count=len(questions),
        vectorized_count=sum(1 for embedding in embeddings if embedding),
        questions=questions,
    )
