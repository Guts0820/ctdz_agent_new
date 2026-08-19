from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.models import KnowledgePoint, KnowledgePointResponse, KnowledgeHierarchyNode

router = APIRouter(prefix="/api", tags=["knowledge_points"])

@router.get("/knowledge_points", response_model=KnowledgePointResponse)
def get_knowledge_points(
    grade: Optional[int] = Query(None, description="年级筛选"),
    semester: Optional[str] = Query(None, description="学期筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    skip = (page - 1) * page_size
    
    query = """
        MATCH (k:KnowledgePoint)
        WHERE 1=1
        """
    
    params = {}
    
    if grade is not None:
        query += " AND k.grade = $grade"
        params["grade"] = grade
    
    if semester is not None:
        query += " AND k.semester = $semester"
        params["semester"] = semester
    
    query_count = query + " RETURN count(k) as total"
    count_result = neo4j_conn.query(query_count, params)
    total = count_result[0]["total"] if count_result else 0
    
    query += " RETURN k ORDER BY k.id SKIP $skip LIMIT $limit"
    params["skip"] = skip
    params["limit"] = page_size
    
    results = neo4j_conn.query(query, params)
    
    knowledge_points = []
    for record in results:
        k = record.get("k", {})
        knowledge_points.append(KnowledgePoint(
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
    
    return KnowledgePointResponse(data=knowledge_points, total=total)

@router.get("/knowledge_points/{knowledge_id}", response_model=KnowledgePoint)
def get_knowledge_point(knowledge_id: str):
    query = """
        MATCH (k:KnowledgePoint {id: $knowledge_id})
        RETURN k
    """
    
    results = neo4j_conn.query(query, {"knowledge_id": knowledge_id})
    
    if not results:
        raise HTTPException(status_code=404, detail=f"知识点 {knowledge_id} 不存在")
    
    k = results[0].get("k", {})
    return KnowledgePoint(
        id=k.get("id"),
        title=k.get("title"),
        description=k.get("description"),
        grade=k.get("grade"),
        semester=k.get("semester"),
        content=k.get("content"),
        key_formulas=k.get("key_formulas"),
        common_mistakes=k.get("common_mistakes"),
        teaching_points=k.get("teaching_points")
    )

@router.get("/knowledge_hierarchy", response_model=List[KnowledgeHierarchyNode])
def get_knowledge_hierarchy(grade: Optional[int] = Query(None)):
    query = """
        MATCH (child:KnowledgePoint)-[:IS_A]->(parent:KnowledgePoint)
        """
    
    if grade is not None:
        query += " WHERE child.grade = $grade"
    
    query += " RETURN child, parent"
    
    params = {"grade": grade} if grade else {}
    results = neo4j_conn.query(query, params)
    
    node_map = {}
    
    for record in results:
        child = record.get("child", {})
        parent = record.get("parent", {})
        
        child_id = child.get("id", "")
        parent_id = parent.get("id", "")
        
        if child_id not in node_map:
            node_map[child_id] = {
                "id": child_id,
                "title": child.get("title", ""),
                "grade": child.get("grade"),
                "children": []
            }
        
        if parent_id not in node_map:
            node_map[parent_id] = {
                "id": parent_id,
                "title": parent.get("title", ""),
                "grade": parent.get("grade"),
                "children": []
            }
        
        if child_id not in [c["id"] for c in node_map[parent_id]["children"]]:
            node_map[parent_id]["children"].append(node_map[child_id])
    
    roots = [node_map[k] for k in node_map if not any(k in [c["id"] for c in node_map[p]["children"]] for p in node_map)]
    
    return roots
