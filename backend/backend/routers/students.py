from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from database_neo4j import neo4j_conn

router = APIRouter(prefix="/api/students", tags=["students"])

@router.get("/")
def get_students(
    grade: Optional[int] = Query(None, description="年级筛选"),
    class_name: Optional[str] = Query(None, description="班级名称筛选")
):
    query = "MATCH (s:Student) WHERE 1=1"
    params = {}

    if grade is not None:
        query += " AND s.grade = $grade"
        params["grade"] = grade

    if class_name is not None:
        query += " AND s.class_name = $class_name"
        params["class_name"] = class_name

    query += " RETURN s.id as id, s.name as name, s.grade as grade, s.class_name as class_name, s.gender as gender, s.school as school ORDER BY s.id"

    try:
        results = neo4j_conn.query(query, params)
        students = []
        for r in results:
            s = r
            students.append({
                "id": s["id"],
                "name": s["name"],
                "grade": s["grade"],
                "class_name": s["class_name"],
                "gender": s.get("gender", ""),
                "school": s.get("school", "")
            })
        return {"total": len(students), "data": students}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/classes")
def get_classes():
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student)
            RETURN s.class_name as class_name, s.grade as grade, count(s) as student_count
            ORDER BY s.grade, s.class_name
        """)
        classes = []
        for r in results:
            classes.append({
                "class_name": r["class_name"],
                "grade": r["grade"],
                "student_count": r["student_count"]
            })
        return {"total": len(classes), "data": classes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{student_id}")
def get_student(student_id: str):
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student {id: $student_id})
            RETURN s
        """, {"student_id": student_id})
        if not results:
            raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")
        s = results[0]["s"]
        return {
            "id": s["id"],
            "name": s["name"],
            "grade": s["grade"],
            "class_name": s["class_name"],
            "gender": s.get("gender", ""),
            "school": s.get("school", ""),
            "birth_date": s.get("birth_date", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{student_id}/mastery")
def get_student_mastery(student_id: str):
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student {id: $student_id})-[m:MASTERY]->(kp:KnowledgePoint)
            RETURN kp.id as knowledge_id, kp.title as title, kp.grade as grade,
                   m.mastery_level as mastery_level
            ORDER BY m.mastery_level ASC
        """, {"student_id": student_id})
        mastery_list = []
        for r in results:
            mastery_list.append({
                "knowledge_id": r["knowledge_id"],
                "title": r["title"],
                "grade": r.get("grade"),
                "mastery_level": r["mastery_level"]
            })
        return {"student_id": student_id, "mastery_data": mastery_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{student_id}/weak")
def get_student_weak_points(
    student_id: str,
    threshold: int = Query(60, description="掌握度阈值")
):
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student {id: $student_id})-[m:MASTERY]->(kp:KnowledgePoint)
            WHERE m.mastery_level < $threshold
            RETURN kp.id as knowledge_id, kp.title as title, kp.grade as grade,
                   m.mastery_level as mastery_level
            ORDER BY m.mastery_level ASC
        """, {"student_id": student_id, "threshold": threshold})
        weak_list = []
        for r in results:
            weak_list.append({
                "knowledge_id": r["knowledge_id"],
                "title": r["title"],
                "grade": r.get("grade"),
                "mastery_level": r["mastery_level"]
            })
        return {"student_id": student_id, "weak_points": weak_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/class/{class_name}")
def get_class_students(class_name: str):
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student {class_name: $class_name})
            RETURN s.id as id, s.name as name, s.grade as grade,
                   s.class_name as class_name, s.gender as gender
            ORDER BY s.id
        """, {"class_name": class_name})
        students = []
        for r in results:
            students.append({
                "id": r["id"],
                "name": r["name"],
                "grade": r["grade"],
                "class_name": r["class_name"],
                "gender": r.get("gender", "")
            })
        return {"class_name": class_name, "total": len(students), "data": students}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/class/{class_name}/mastery")
def get_class_mastery(class_name: str):
    try:
        results = neo4j_conn.query("""
            MATCH (s:Student {class_name: $class_name})-[m:MASTERY]->(kp:KnowledgePoint)
            RETURN kp.id as knowledge_id, kp.title as title,
                   avg(m.mastery_level) as avg_mastery,
                   count(m) as student_count
            ORDER BY avg_mastery ASC
        """, {"class_name": class_name})
        class_mastery = []
        for r in results:
            class_mastery.append({
                "knowledge_id": r["knowledge_id"],
                "title": r["title"],
                "avg_mastery": round(r["avg_mastery"], 1),
                "student_count": r["student_count"]
            })
        return {"class_name": class_name, "mastery_data": class_mastery}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
