from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional, List
from database import neo4j_conn
from models import Question, QuestionResponse, RecommendRequest, RecommendResponse, KnowledgePoint

router = APIRouter(prefix="/api", tags=["questions"])

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
        questions.append(Question(
            id=q.get("id"),
            text=q.get("text"),
            answer=q.get("answer"),
            difficulty=q.get("difficulty"),
            grade=q.get("grade"),
            semester=q.get("semester"),
            source=q.get("source"),
            knowledge_id=q.get("knowledge_id"),
            name=q.get("name"),
            type=q.get("type"),
            image_path=q.get("image_path"),
            answer_steps=q.get("answer_steps")
        ))
    
    return QuestionResponse(data=questions, total=total)

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
    return Question(
        id=q.get("id"),
        text=q.get("text"),
        answer=q.get("answer"),
        difficulty=q.get("difficulty"),
        grade=q.get("grade"),
        semester=q.get("semester"),
        source=q.get("source"),
        knowledge_id=q.get("knowledge_id"),
        name=q.get("name"),
        type=q.get("type"),
        image_path=q.get("image_path"),
        answer_steps=q.get("answer_steps")
    )

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
        questions.append(Question(
            id=q.get("id"),
            text=q.get("text"),
            answer=q.get("answer"),
            difficulty=q.get("difficulty"),
            grade=q.get("grade"),
            semester=q.get("semester"),
            source=q.get("source"),
            knowledge_id=q.get("knowledge_id"),
            name=q.get("name"),
            type=q.get("type"),
            image_path=q.get("image_path"),
            answer_steps=q.get("answer_steps")
        ))
    
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