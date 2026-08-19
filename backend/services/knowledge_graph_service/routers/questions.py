import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, List

from fastapi import APIRouter, Query, Body, HTTPException

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.models import (
    Question,
    QuestionCandidateResponse,
    QuestionResponse,
    RecommendRequest,
    RecommendResponse,
    KnowledgePoint,
)
from backend.services.knowledge_graph_service.embedding import embed_query_text
from backend.shared.config import KG_VECTOR_INDEX_NAME, KG_VECTOR_TOP_K

router = APIRouter(prefix="/api", tags=["questions"])


def _to_question(question: dict) -> Question:
    return Question(
        id=question.get("id"),
        text=question.get("text"),
        answer=question.get("answer"),
        difficulty=question.get("difficulty"),
        grade=question.get("grade"),
        semester=question.get("semester"),
        source=question.get("source"),
        knowledge_id=question.get("knowledge_id"),
        name=question.get("name"),
        type=question.get("type"),
        image_path=question.get("image_path"),
        answer_steps=question.get("answer_steps"),
        aliases=question.get("aliases"),
        explanation=question.get("explanation"),
    )


def normalize_question_text(question_text: str) -> str:
    """Normalize OCR punctuation and spacing without changing numbers or words."""
    normalized = unicodedata.normalize("NFKC", question_text).lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized, flags=re.UNICODE)


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[index : index + 2] for index in range(len(text) - 1)}


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    left_bigrams = _bigrams(left)
    right_bigrams = _bigrams(right)
    bigram_union = left_bigrams | right_bigrams
    bigram_score = len(left_bigrams & right_bigrams) / len(bigram_union) if bigram_union else 0.0
    left_chars = set(left)
    right_chars = set(right)
    char_union = left_chars | right_chars
    char_score = len(left_chars & right_chars) / len(char_union) if char_union else 0.0
    sequence_score = SequenceMatcher(None, left, right).ratio()
    return round(sequence_score * 0.45 + bigram_score * 0.35 + char_score * 0.20, 6)


def _score_question(question_text: str, question: dict) -> tuple[float, str]:
    query = normalize_question_text(question_text)
    variants = [question.get("text", ""), *(question.get("aliases") or [])]
    scored = [
        (normalize_question_text(str(variant)), variant)
        for variant in variants
        if str(variant).strip()
    ]
    if not scored:
        return 0.0, "hybrid_lexical"
    scores = [(_text_similarity(query, normalized), variant) for normalized, variant in scored]
    best_score, best_variant = max(scores, key=lambda item: item[0])
    if normalize_question_text(str(best_variant)) == query:
        return best_score, "normalized_exact"
    return best_score, "hybrid_lexical"


def search_vector_candidates(question_text: str, limit: int = KG_VECTOR_TOP_K) -> list[dict]:
    embedding = embed_query_text(question_text)
    if not embedding:
        return []
    rows = neo4j_conn.query(
        """
        CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
        YIELD node, score
        RETURN node, score
        """,
        {
            "index_name": KG_VECTOR_INDEX_NAME,
            "limit": max(1, min(limit, 100)),
            "embedding": embedding,
        },
    )
    candidates = []
    for row in rows:
        question = row.get("node", {})
        candidate = _to_question(question).model_dump()
        candidate.update({
            "retrieval_score": round(float(row.get("score", 0.0)), 6),
            "match_type": "vector",
        })
        candidates.append(candidate)
    return candidates


def search_question_candidates(question_text: str, limit: int = 5) -> list[dict]:
    """Recall graph questions for LLM reranking using hybrid lexical scores."""
    normalized_text = question_text.strip()
    if not normalized_text:
        raise HTTPException(status_code=422, detail="题干不能为空，无法检索知识图谱题目")
    try:
        vector_candidates = search_vector_candidates(normalized_text, limit)
    except Exception:
        vector_candidates = []

    rows = neo4j_conn.query(
        "MATCH (q:Question) WHERE q.text IS NOT NULL RETURN q",
        {},
    )
    candidates_by_id: dict[str, dict] = {
        str(candidate.get("id")): candidate
        for candidate in vector_candidates
        if candidate.get("id")
    }
    for row in rows:
        question = row.get("q", {})
        score, match_type = _score_question(normalized_text, question)
        if score <= 0:
            continue
        candidate = _to_question(question).model_dump()
        candidate.update({"retrieval_score": score, "match_type": match_type})
        question_id = str(candidate.get("id", ""))
        existing = candidates_by_id.get(question_id)
        if existing is None or score > existing["retrieval_score"]:
            candidates_by_id[question_id] = candidate
    candidates = list(candidates_by_id.values())
    candidates.sort(key=lambda item: (-item["retrieval_score"], str(item.get("id", ""))))
    return candidates[: max(1, min(limit, 10))]


def resolve_question_by_text(question_text: str) -> Question:
    normalized_text = question_text.strip()
    if not normalized_text:
        raise HTTPException(status_code=422, detail="题干不能为空，无法匹配知识图谱题目")

    results = neo4j_conn.query(
        """
        MATCH (q:Question {text: $question_text})
        RETURN q
        LIMIT 1
        """,
        {"question_text": normalized_text},
    )
    if not results:
        raise HTTPException(status_code=404, detail="知识图谱中不存在与题干完全匹配的题目")
    return _to_question(results[0].get("q", {}))

@router.get("/questions", response_model=QuestionResponse)
def get_questions(
    grade: Optional[int] = Query(None, description="年级筛选"),
    semester: Optional[str] = Query(None, description="学期筛选"),
    difficulty: Optional[int] = Query(None, description="难度筛选"),
    knowledge_id: Optional[str] = Query(None, description="知识点ID筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    skip = (page - 1) * page_size
    
    query = """
        MATCH (q:Question)
        WHERE 1=1
        """
    
    params = {}
    
    if grade is not None:
        query += " AND q.grade = $grade"
        params["grade"] = grade
    
    if semester is not None:
        query += " AND q.semester = $semester"
        params["semester"] = semester
    
    if difficulty is not None:
        query += " AND q.difficulty = $difficulty"
        params["difficulty"] = difficulty
    
    if knowledge_id is not None:
        query = """
            MATCH (q:Question)-[:EXAMINES]->(k:KnowledgePoint {id: $knowledge_id})
            WHERE 1=1
            """
        
        if grade is not None:
            query += " AND q.grade = $grade"
        
        if semester is not None:
            query += " AND q.semester = $semester"
        
        if difficulty is not None:
            query += " AND q.difficulty = $difficulty"
    
    query_count = query + " RETURN count(q) as total"
    count_result = neo4j_conn.query(query_count, params)
    total = count_result[0]["total"] if count_result else 0
    
    query += " RETURN q ORDER BY q.id SKIP $skip LIMIT $limit"
    params["skip"] = skip
    params["limit"] = page_size
    
    results = neo4j_conn.query(query, params)
    
    questions = []
    for record in results:
        q = record.get("q", {})
        questions.append(_to_question(q))
    
    return QuestionResponse(data=questions, total=total)


@router.get("/questions/resolve", response_model=Question)
def resolve_question(question_text: str = Query(..., alias="text", min_length=1)):
    """Resolve an OCR question stem to the graph record that owns its answer."""
    return resolve_question_by_text(question_text)


@router.get("/questions/candidates", response_model=QuestionCandidateResponse)
def question_candidates(
    question_text: str = Query(..., alias="text", min_length=1),
    limit: int = Query(5, ge=1, le=10),
):
    candidates = search_question_candidates(question_text, limit)
    return QuestionCandidateResponse(data=candidates, total=len(candidates))

@router.get("/questions/{question_id}", response_model=Question)
def get_question(question_id: str):
    query = """
        MATCH (q:Question {id: $question_id})
        RETURN q
    """
    
    results = neo4j_conn.query(query, {"question_id": question_id})
    
    if not results:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
    
    q = results[0].get("q", {})
    return _to_question(q)

@router.post("/recommend", response_model=RecommendResponse)
def recommend_questions(request: RecommendRequest):
    knowledge_ids = request.knowledge_ids
    count = request.count or 5
    
    questions_query = """
        MATCH (q:Question)-[:EXAMINES]->(k:KnowledgePoint)
        WHERE k.id IN $knowledge_ids
        RETURN q ORDER BY q.difficulty LIMIT $limit
    """
    
    questions_results = neo4j_conn.query(questions_query, {"knowledge_ids": knowledge_ids, "limit": count})
    
    questions = []
    for record in questions_results:
        q = record.get("q", {})
        questions.append(_to_question(q))
    
    related_knowledge_query = """
        MATCH (k1:KnowledgePoint)-[:RELATED_TO]->(k2:KnowledgePoint)
        WHERE k1.id IN $knowledge_ids
        RETURN k2 LIMIT $limit
    """
    
    related_results = neo4j_conn.query(related_knowledge_query, {"knowledge_ids": knowledge_ids, "limit": count})
    
    related_knowledge = []
    for record in related_results:
        k = record.get("k2", {})
        related_knowledge.append(KnowledgePoint(
            id=k.get("id"),
            title=k.get("title"),
            description=k.get("description"),
            grade=k.get("grade"),
            semester=k.get("semester"),
            content=k.get("content"),
            key_formulas=k.get("key_formulas"),
            common_mistakes=k.get("common_mistakes"),
            teaching_points=k.get("teaching_points")
        ))
    
    return RecommendResponse(recommended_questions=questions, related_knowledge_points=related_knowledge)
