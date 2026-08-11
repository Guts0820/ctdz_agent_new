from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional, List
from database_neo4j import neo4j_conn
from models import Question, QuestionResponse, RecommendRequest, RecommendResponse, KnowledgePoint, VisualSearchRequest, VisualSearchResponse, SimilarQuestion
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from multimodal_embedding import MultimodalEmbeddingExtractor
    embedding_extractor = MultimodalEmbeddingExtractor(offline_mode=True)
except ImportError:
    embedding_extractor = None

router = APIRouter(prefix="/api", tags=["questions"])

def build_question_from_record(q):
    image_path = q.get("image_path")
    if not image_path or image_path == 'null':
        q_id = q.get("id", "")
        image_path = f"/images/{q_id}.png" if q_id else None
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
        image_path=image_path,
        answer_steps=q.get("answer_steps"),
        ocr_text=q.get("ocr_text"),
        visual_description=q.get("visual_description"),
        image_embedding=q.get("image_embedding")
    )

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
    
    try:
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
            questions.append(build_question_from_record(q))
    except Exception:
        # knowledge_id 查不到或 Neo4j 查询错误时降级为空结果
        total = 0
        questions = []
    
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
    return build_question_from_record(q)

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
        questions.append(build_question_from_record(q))
    
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

@router.post("/visual-search", response_model=VisualSearchResponse)
def visual_search(request: VisualSearchRequest):
    if embedding_extractor is None:
        raise HTTPException(status_code=503, detail="视觉搜索功能不可用：缺少 multimodal_embedding 模块")
    query_type = request.query_type
    top_k = request.top_k or 5
    grade = request.grade
    semester = request.semester
    
    if query_type == "text":
        if not request.query:
            raise HTTPException(status_code=400, detail="text查询需要提供query参数")
        
        text_embedding = embedding_extractor.extract_text_embedding(request.query)
        if not text_embedding:
            raise HTTPException(status_code=500, detail="文本嵌入提取失败")
        
        base_query = """
            CALL db.index.vector.queryNodes('question_image_index', $top_k, $embedding)
            YIELD node, score
        """
        
        if grade or semester:
            base_query += " WHERE 1=1"
            if grade:
                base_query += " AND node.grade = $grade"
            if semester:
                base_query += " AND node.semester = $semester"
        
        base_query += " RETURN node, score ORDER BY score DESC"
        
        params = {
            "top_k": top_k,
            "embedding": text_embedding
        }
        
        if grade:
            params["grade"] = grade
        if semester:
            params["semester"] = semester
        
        results = neo4j_conn.query(base_query, params)
    
    elif query_type == "image":
        if not request.question_id:
            raise HTTPException(status_code=400, detail="image查询需要提供question_id参数")
        
        get_embedding_query = """
            MATCH (q:Question {id: $question_id})
            RETURN q.image_embedding as embedding
        """
        
        embedding_result = neo4j_conn.query(get_embedding_query, {"question_id": request.question_id})
        
        if not embedding_result or not embedding_result[0].get("embedding"):
            raise HTTPException(status_code=404, detail=f"题目 {request.question_id} 没有图像嵌入")
        
        image_embedding = embedding_result[0]["embedding"]
        
        base_query = """
            CALL db.index.vector.queryNodes('question_image_index', $top_k, $embedding)
            YIELD node, score
            WHERE node.id <> $exclude_id
        """
        
        if grade or semester:
            if grade:
                base_query += " AND node.grade = $grade"
            if semester:
                base_query += " AND node.semester = $semester"
        
        base_query += " RETURN node, score ORDER BY score DESC"
        
        params = {
            "top_k": top_k,
            "embedding": image_embedding,
            "exclude_id": request.question_id
        }
        
        if grade:
            params["grade"] = grade
        if semester:
            params["semester"] = semester
        
        results = neo4j_conn.query(base_query, params)
    
    else:
        raise HTTPException(status_code=400, detail="query_type只能是text或image")
    
    similar_questions = []
    for record in results:
        q = record.get("node", {})
        score = record.get("score", 0.0)
        similar_questions.append(SimilarQuestion(
            question=build_question_from_record(q),
            similarity=score
        ))
    
    return VisualSearchResponse(results=similar_questions)

@router.get("/questions/{question_id}/similar", response_model=VisualSearchResponse)
def get_similar_questions(
    question_id: str,
    top_k: Optional[int] = Query(5, ge=1, le=20, description="返回数量"),
    grade: Optional[int] = Query(None, description="年级筛选"),
    semester: Optional[str] = Query(None, description="学期筛选")
):
    if embedding_extractor is None:
        raise HTTPException(status_code=503, detail="视觉搜索功能不可用：缺少 multimodal_embedding 模块")
    get_embedding_query = """
        MATCH (q:Question {id: $question_id})
        RETURN q.image_embedding as embedding, q.grade as grade, q.semester as semester
    """
    
    embedding_result = neo4j_conn.query(get_embedding_query, {"question_id": question_id})
    
    if not embedding_result:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
    
    image_embedding = embedding_result[0].get("embedding")
    if not image_embedding:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 没有图像嵌入")
    
    if grade is None:
        grade = embedding_result[0].get("grade")
    if semester is None:
        semester = embedding_result[0].get("semester")
    
    base_query = """
        CALL db.index.vector.queryNodes('question_image_index', $top_k, $embedding)
        YIELD node, score
        WHERE node.id <> $exclude_id
    """
    
    if grade:
        base_query += " AND node.grade = $grade"
    if semester:
        base_query += " AND node.semester = $semester"
    
    base_query += " RETURN node, score ORDER BY score DESC"
    
    params = {
        "top_k": top_k,
        "embedding": image_embedding,
        "exclude_id": question_id
    }
    
    if grade:
        params["grade"] = grade
    if semester:
        params["semester"] = semester
    
    results = neo4j_conn.query(base_query, params)
    
    similar_questions = []
    for record in results:
        q = record.get("node", {})
        score = record.get("score", 0.0)
        similar_questions.append(SimilarQuestion(
            question=build_question_from_record(q),
            similarity=score
        ))
    
    return VisualSearchResponse(results=similar_questions)