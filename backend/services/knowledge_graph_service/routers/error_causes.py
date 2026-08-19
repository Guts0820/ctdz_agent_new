from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional, List
from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.models import ErrorCause, ErrorCauseResponse, AnalyzeRequest, AnalyzeResponse, WeakKnowledgePoint

router = APIRouter(prefix="/api", tags=["error_causes"])

@router.get("/error_causes", response_model=ErrorCauseResponse)
def get_error_causes(
    grade_range: Optional[str] = Query(None, description="年级范围筛选"),
    knowledge_scope: Optional[str] = Query(None, description="知识点范围筛选"),
    level1: Optional[str] = Query(None, description="一级分类筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    skip = (page - 1) * page_size
    
    query = """
        MATCH (e:ErrorCause)
        WHERE 1=1
        """
    
    params = {}
    
    if grade_range is not None:
        query += " AND e.grade_range = $grade_range"
        params["grade_range"] = grade_range
    
    if knowledge_scope is not None:
        query += " AND e.knowledge_scope = $knowledge_scope"
        params["knowledge_scope"] = knowledge_scope
    
    if level1 is not None:
        query += " AND e.level1 = $level1"
        params["level1"] = level1
    
    query_count = query + " RETURN count(e) as total"
    count_result = neo4j_conn.query(query_count, params)
    total = count_result[0]["total"] if count_result else 0
    
    query += " RETURN e ORDER BY e.id SKIP $skip LIMIT $limit"
    params["skip"] = skip
    params["limit"] = page_size
    
    results = neo4j_conn.query(query, params)
    
    error_causes = []
    for record in results:
        e = record.get("e", {})
        error_causes.append(ErrorCause(
            id=e.get("id"),
            level1=e.get("level1"),
            level2=e.get("level2"),
            level3=e.get("level3"),
            criteria=e.get("criteria"),
            grade_range=e.get("grade_range"),
            knowledge_scope=e.get("knowledge_scope"),
            example=e.get("example"),
            name=e.get("name")
        ))
    
    return ErrorCauseResponse(data=error_causes, total=total)

@router.get("/error_causes/{error_cause_id}", response_model=ErrorCause)
def get_error_cause(error_cause_id: str):
    query = """
        MATCH (e:ErrorCause {id: $error_cause_id})
        RETURN e
    """
    
    results = neo4j_conn.query(query, {"error_cause_id": error_cause_id})
    
    if not results:
        raise HTTPException(status_code=404, detail=f"错因 {error_cause_id} 不存在")
    
    e = results[0].get("e", {})
    return ErrorCause(
        id=e.get("id"),
        level1=e.get("level1"),
        level2=e.get("level2"),
        level3=e.get("level3"),
        criteria=e.get("criteria"),
        grade_range=e.get("grade_range"),
        knowledge_scope=e.get("knowledge_scope"),
        example=e.get("example"),
        name=e.get("name")
    )

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_mistakes(request: AnalyzeRequest):
    question_ids = request.question_ids
    
    knowledge_query = """
        MATCH (q:Question)-[:EXAMINES]->(k:KnowledgePoint)
        WHERE q.id IN $question_ids
        RETURN k.id as knowledge_id, k.title as title, count(q) as error_count
        ORDER BY error_count DESC
    """
    
    knowledge_results = neo4j_conn.query(knowledge_query, {"question_ids": question_ids})
    
    weak_knowledge_points = []
    for record in knowledge_results:
        weak_knowledge_points.append(WeakKnowledgePoint(
            knowledge_id=record.get("knowledge_id", ""),
            title=record.get("title", ""),
            error_count=record.get("error_count", 0),
            related_questions_count=0
        ))
    
    related_questions_count_query = """
        MATCH (q:Question)-[:EXAMINES]->(k:KnowledgePoint)
        WHERE k.id IN $knowledge_ids
        RETURN k.id as knowledge_id, count(q) as total_count
    """
    
    knowledge_ids = [wkp.knowledge_id for wkp in weak_knowledge_points]
    if knowledge_ids:
        count_results = neo4j_conn.query(related_questions_count_query, {"knowledge_ids": knowledge_ids})
        count_map = {r["knowledge_id"]: r["total_count"] for r in count_results}
        
        for wkp in weak_knowledge_points:
            wkp.related_questions_count = count_map.get(wkp.knowledge_id, 0)
    
    recommended_review_plan = []
    for wkp in weak_knowledge_points[:3]:
        recommended_review_plan.append(f"重点复习知识点：{wkp.title} (ID: {wkp.knowledge_id})")
        recommended_review_plan.append(f"该知识点共做错 {wkp.error_count} 道题")
    
    return AnalyzeResponse(
        weak_knowledge_points=weak_knowledge_points,
        recommended_review_plan=recommended_review_plan
    )
