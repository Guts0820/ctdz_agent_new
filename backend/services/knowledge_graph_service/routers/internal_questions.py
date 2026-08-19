import hashlib

from fastapi import APIRouter

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.embedding import embed_questions
from backend.services.knowledge_graph_service.models import (
    Question,
    StandardAnswerUpsertRequest,
    StandardAnswerUpsertResponse,
)


router = APIRouter(prefix="/internal/api", tags=["internal-questions"])


@router.post("/questions/standard-answer", response_model=StandardAnswerUpsertResponse)
def upsert_standard_answers(request: StandardAnswerUpsertRequest) -> StandardAnswerUpsertResponse:
    base_items = [
        {
            "id": f"TQ{hashlib.sha256(item.text.encode('utf-8')).hexdigest()[:12].upper()}",
            "text": item.text.strip(),
            "explanation": item.explanation.strip(),
            "answer": item.answer.strip(),
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
        MERGE (q:Question {text: item.text})
        ON CREATE SET q.id = item.id
        SET q.answer = item.answer,
            q.answer_steps = item.explanation,
            q.explanation = item.explanation,
            q.embedding = item.embedding,
            q.source = 'teacher_upload',
            q.import_batch = 'teacher-standard-answer-v1'
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
