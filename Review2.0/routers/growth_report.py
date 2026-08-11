from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict
from database import neo4j_conn
from user_database import user_db
from models import (
    GrowthReport, FiveDimensionScore, WeakKnowledgeArea,
    ProgressItem, LearningPathNode, KnowledgePoint
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/api", tags=["growth_report"])

OPERATION_KNOWLEDGE_KEYWORDS = ["计算", "运算", "加减", "乘除", "竖式", "口算", "笔算", "混合运算"]
LOGIC_KNOWLEDGE_KEYWORDS = ["推理", "规律", "逻辑", "排列", "组合", "归纳", "演绎", "判断"]
SPATIAL_KNOWLEDGE_KEYWORDS = ["图形", "几何", "空间", "位置", "方向", "对称", "面积", "体积", "周长"]
LANGUAGE_KNOWLEDGE_KEYWORDS = ["应用题", "解决问题", "文字题", "理解", "表达", "描述"]

def calculate_operation_ability(user_id: int) -> int:
    progress = user_db.get_learning_progress(user_id)
    if not progress:
        return 0
    
    operation_points = []
    for p in progress:
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k.title as title",
            {"id": p["knowledge_id"]}
        )
        if kp:
            title = kp[0]["title"]
            if any(keyword in title for keyword in OPERATION_KNOWLEDGE_KEYWORDS):
                operation_points.append(p["mastery_level"])
    
    if not operation_points:
        return 0
    
    return round(sum(operation_points) / len(operation_points))

def calculate_logic_ability(user_id: int) -> int:
    progress = user_db.get_learning_progress(user_id)
    if not progress:
        return 0
    
    logic_points = []
    for p in progress:
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k.title as title",
            {"id": p["knowledge_id"]}
        )
        if kp:
            title = kp[0]["title"]
            if any(keyword in title for keyword in LOGIC_KNOWLEDGE_KEYWORDS):
                logic_points.append(p["mastery_level"])
    
    if not logic_points:
        return 0
    
    return round(sum(logic_points) / len(logic_points))

def calculate_spatial_ability(user_id: int) -> int:
    progress = user_db.get_learning_progress(user_id)
    if not progress:
        return 0
    
    spatial_points = []
    for p in progress:
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k.title as title",
            {"id": p["knowledge_id"]}
        )
        if kp:
            title = kp[0]["title"]
            if any(keyword in title for keyword in SPATIAL_KNOWLEDGE_KEYWORDS):
                spatial_points.append(p["mastery_level"])
    
    if not spatial_points:
        return 0
    
    return round(sum(spatial_points) / len(spatial_points))

def calculate_language_reasoning(user_id: int) -> int:
    progress = user_db.get_learning_progress(user_id)
    if not progress:
        return 0
    
    language_points = []
    for p in progress:
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k.title as title",
            {"id": p["knowledge_id"]}
        )
        if kp:
            title = kp[0]["title"]
            if any(keyword in title for keyword in LANGUAGE_KNOWLEDGE_KEYWORDS):
                language_points.append(p["mastery_level"])
    
    if not language_points:
        return 0
    
    return round(sum(language_points) / len(language_points))

def calculate_resilience(user_id: int) -> int:
    wrong_questions = user_db.get_wrong_questions(user_id)
    reviewed_count = sum(1 for wq in wrong_questions if wq["reviewed"])
    total_wrong = len(wrong_questions)
    
    answer_records = user_db.get_answer_records(user_id, limit=100)
    correct_count = sum(1 for r in answer_records if r["is_correct"])
    total_answers = len(answer_records)
    
    review_plans = user_db.get_pending_reviews(user_id)
    completed_plans = 0
    all_plans = user_db.query("""
        SELECT COUNT(*) as total FROM review_plan WHERE user_id = ?
    """, (user_id,))
    total_plans = all_plans[0]["total"] if all_plans else 0
    
    if total_wrong > 0:
        review_rate = reviewed_count / total_wrong
    else:
        review_rate = 0.5
    
    if total_answers > 0:
        persist_rate = min(correct_count / max(total_answers - correct_count, 1), 2.0)
    else:
        persist_rate = 0.5
    
    if total_plans > 0:
        plan_completion_rate = completed_plans / total_plans
    else:
        plan_completion_rate = 0.5
    
    resilience_score = round((review_rate * 0.4 + persist_rate * 0.4 + plan_completion_rate * 0.2) * 100)
    return min(max(resilience_score, 0), 100)

def get_weak_knowledge_areas(user_id: int, threshold: int = 60) -> List[WeakKnowledgeArea]:
    weak_points = user_db.get_weak_knowledge_points(user_id, threshold)
    result = []
    
    for wp in weak_points:
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k",
            {"id": wp["knowledge_id"]}
        )
        
        if not kp:
            continue
        
        k = kp[0]["k"]
        suggestions = []
        
        if wp["mastery_level"] < 40:
            suggestions.append("建议重新学习基础知识，理解核心概念")
            suggestions.append("多做基础练习题，巩固知识点")
        elif wp["mastery_level"] < 60:
            suggestions.append("建议重点复习该知识点的典型例题")
            suggestions.append("尝试使用不同方法解题，加深理解")
        
        wrong_count = wp["wrong_count"]
        if wrong_count >= 3:
            suggestions.append("建议查看错题解析，分析错误原因")
        
        difficulty = "基础" if wp["mastery_level"] < 40 else "进阶" if wp["mastery_level"] < 60 else "提高"
        
        result.append(WeakKnowledgeArea(
            knowledge_id=wp["knowledge_id"],
            title=k.get("title", ""),
            mastery_level=wp["mastery_level"],
            error_count=wrong_count,
            difficulty=difficulty,
            suggestions=suggestions
        ))
    
    return sorted(result, key=lambda x: x.mastery_level)

def get_recent_progress(user_id: int, days: int = 7) -> List[ProgressItem]:
    progress = user_db.get_learning_progress(user_id)
    if not progress:
        return []
    
    result = []
    
    for p in progress:
        current_mastery = p["mastery_level"]
        correct_count = p["correct_count"]
        wrong_count = p["wrong_count"]
        total = correct_count + wrong_count
        
        if total > 0:
            recent_rate = correct_count / total
            previous_mastery = max(0, current_mastery - round(recent_rate * 15))
        else:
            previous_mastery = max(0, current_mastery - 10)
        
        improvement = current_mastery - previous_mastery
        achieved = current_mastery >= 80
        achieved_at = None
        
        kp = neo4j_conn.query(
            "MATCH (k:KnowledgePoint {id: $id}) RETURN k.title as title",
            {"id": p["knowledge_id"]}
        )
        title = kp[0]["title"] if kp else "未知知识点"
        
        if improvement >= 5 or achieved:
            result.append(ProgressItem(
                knowledge_id=p["knowledge_id"],
                title=title,
                previous_mastery=previous_mastery,
                current_mastery=current_mastery,
                improvement=improvement,
                achieved=achieved,
                achieved_at=achieved_at
            ))
    
    return sorted(result, key=lambda x: x.improvement, reverse=True)[:5]

def get_learning_path(user_id: int) -> List[LearningPathNode]:
    user = user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    grade = user.get("grade", 1)
    semester = user.get("semester", "上册")
    
    progress = user_db.get_learning_progress(user_id)
    mastered_knowledge = {p["knowledge_id"] for p in progress if p["mastery_level"] >= 80}
    weak_knowledge = {p["knowledge_id"] for p in progress if p["mastery_level"] < 60}
    
    query = """
        MATCH (k:KnowledgePoint)
        WHERE k.grade = $grade
        OPTIONAL MATCH (k)-[:IS_A]->(parent:KnowledgePoint)
        RETURN k, parent
        ORDER BY k.id
    """
    
    results = neo4j_conn.query(query, {"grade": grade})
    
    knowledge_map = {}
    for record in results:
        k = record.get("k", {})
        parent = record.get("parent", None)
        knowledge_map[k.get("id", "")] = {
            "id": k.get("id", ""),
            "title": k.get("title", ""),
            "description": k.get("description", ""),
            "parent_id": parent.get("id", "") if parent else None,
            "mastered": k.get("id", "") in mastered_knowledge,
            "weak": k.get("id", "") in weak_knowledge
        }
    
    path_nodes = []
    order = 1
    
    for kid, info in knowledge_map.items():
        if info["weak"]:
            node_type = "weak"
            estimated_time = "45分钟"
        elif not info["mastered"]:
            node_type = "normal"
            estimated_time = "30分钟"
        else:
            node_type = "mastered"
            estimated_time = "15分钟"
        
        prerequisites = []
        if info["parent_id"] and info["parent_id"] in knowledge_map:
            prerequisites.append(info["parent_id"])
        
        path_nodes.append(LearningPathNode(
            knowledge_id=kid,
            title=info["title"],
            description=info["description"],
            order=order,
            estimated_time=estimated_time,
            type=node_type,
            prerequisites=prerequisites
        ))
        order += 1
    
    path_nodes.sort(key=lambda x: (x.type != "weak", x.order))
    
    weak_nodes = [n for n in path_nodes if n.type == "weak"]
    normal_nodes = [n for n in path_nodes if n.type == "normal"]
    
    needed = 5 - len(weak_nodes)
    if needed > 0:
        result = weak_nodes + normal_nodes[:needed]
    else:
        result = weak_nodes[:5]
    
    return result

@router.get("/growth_report/{user_id}", response_model=GrowthReport)
def generate_growth_report(user_id: int):
    user = user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    five_dimension_scores = [
        FiveDimensionScore(
            dimension="operation",
            score=calculate_operation_ability(user_id),
            label="运算能力"
        ),
        FiveDimensionScore(
            dimension="logic",
            score=calculate_logic_ability(user_id),
            label="逻辑思维"
        ),
        FiveDimensionScore(
            dimension="spatial",
            score=calculate_spatial_ability(user_id),
            label="空间想象"
        ),
        FiveDimensionScore(
            dimension="language",
            score=calculate_language_reasoning(user_id),
            label="语言推理"
        ),
        FiveDimensionScore(
            dimension="resilience",
            score=calculate_resilience(user_id),
            label="学习韧性"
        )
    ]
    
    weak_knowledge_areas = get_weak_knowledge_areas(user_id)
    recent_progress = get_recent_progress(user_id)
    learning_path = get_learning_path(user_id)
    
    return GrowthReport(
        user_id=user_id,
        username=user.get("username", ""),
        grade=user.get("grade", 1),
        semester=user.get("semester", "上册"),
        report_date=datetime.now().strftime("%Y-%m-%d"),
        five_dimension_scores=five_dimension_scores,
        weak_knowledge_areas=weak_knowledge_areas,
        recent_progress=recent_progress,
        learning_path=learning_path
    )

@router.get("/five_dimension_scores/{user_id}", response_model=List[FiveDimensionScore])
def get_five_dimension_scores(user_id: int):
    user = user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return [
        FiveDimensionScore(
            dimension="operation",
            score=calculate_operation_ability(user_id),
            label="运算能力"
        ),
        FiveDimensionScore(
            dimension="logic",
            score=calculate_logic_ability(user_id),
            label="逻辑思维"
        ),
        FiveDimensionScore(
            dimension="spatial",
            score=calculate_spatial_ability(user_id),
            label="空间想象"
        ),
        FiveDimensionScore(
            dimension="language",
            score=calculate_language_reasoning(user_id),
            label="语言推理"
        ),
        FiveDimensionScore(
            dimension="resilience",
            score=calculate_resilience(user_id),
            label="学习韧性"
        )
    ]

@router.get("/weak_areas/{user_id}", response_model=List[WeakKnowledgeArea])
def get_weak_areas(
    user_id: int,
    threshold: int = Query(60, description="掌握程度阈值")
):
    return get_weak_knowledge_areas(user_id, threshold)

@router.get("/recent_progress/{user_id}", response_model=List[ProgressItem])
def get_recent_progress_endpoint(
    user_id: int,
    days: int = Query(7, description="最近天数")
):
    return get_recent_progress(user_id, days)

@router.get("/learning_path/{user_id}", response_model=List[LearningPathNode])
def get_learning_path_endpoint(user_id: int):
    return get_learning_path(user_id)