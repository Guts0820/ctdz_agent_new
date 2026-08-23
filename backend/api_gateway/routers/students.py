from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from backend.shared.neo4j_connection import neo4j_conn
from backend.api_gateway.services.gateway_database import get_gateway_db

router = APIRouter(prefix="/api/students", tags=["students"])


def _sqlite_students(class_name: str | None = None) -> list[dict]:
    with get_gateway_db() as connection:
        query = "SELECT student_id, student_name, student_grade, student_class, student_gender, student_school FROM students"
        params = ()
        if class_name:
            query += " WHERE student_class = ?"
            params = (class_name,)
        rows = connection.execute(query + " ORDER BY student_id", params).fetchall()
    return [{"id": row[0], "name": row[1], "grade": row[2], "class_name": row[3], "gender": row[4] or "", "school": row[5] or ""} for row in rows]


def _sqlite_mastery(student_id: str, threshold: int | None = None) -> list[dict]:
    with get_gateway_db() as connection:
        query = (
            "SELECT km.knowledge_id, COALESCE(k.knowledge_name, km.knowledge_id), k.grade, "
            "COALESCE(km.master_level * 100, 0) FROM knowledge_mastery km "
            "LEFT JOIN knowledge k ON k.knowledge_id = km.knowledge_id WHERE km.student_id = ?"
        )
        params = [student_id]
        if threshold is not None:
            query += " AND COALESCE(km.master_level * 100, 0) < ?"
            params.append(threshold)
        rows = connection.execute(query + " ORDER BY 4", params).fetchall()
    return [{"knowledge_id": row[0], "title": row[1], "grade": row[2], "mastery_level": round(row[3] or 0, 1)} for row in rows]

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
        if not students:
            students = _sqlite_students(class_name)
        return {"total": len(students), "data": students}
    except Exception as e:
        students = _sqlite_students(class_name)
        return {"total": len(students), "data": students}

@router.get("/classes")
def get_classes(teacher_id: str | None = Query(None)):
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
        if teacher_id:
            with get_gateway_db() as connection:
                rows = connection.execute(
                    "SELECT tc.class_id, tc.class_name, tc.grade, COUNT(s.student_id) student_count "
                    "FROM teacher_class tc LEFT JOIN students s ON s.student_class = tc.class_name "
                    "WHERE tc.teacher_id = ? GROUP BY tc.class_id, tc.class_name, tc.grade ORDER BY tc.class_id",
                    (teacher_id,),
                ).fetchall()
            classes = [{"class_id": row[0], "class_name": row[1], "grade": row[2], "student_count": row[3]} for row in rows]
        elif not classes:
            students = _sqlite_students()
            grouped = {}
            for student in students:
                key = student["class_name"]
                grouped.setdefault(key, {"class_name": key, "grade": student["grade"], "student_count": 0})["student_count"] += 1
            classes = list(grouped.values())
        return {"total": len(classes), "data": classes}
    except Exception as e:
        with get_gateway_db() as connection:
            rows = connection.execute(
                "SELECT class_id, class_name, grade FROM teacher_class WHERE (? IS NULL OR teacher_id = ?) ORDER BY class_id",
                (teacher_id, teacher_id),
            ).fetchall()
        return {"total": len(rows), "data": [{"class_id": row[0], "class_name": row[1], "grade": row[2], "student_count": len(_sqlite_students(row[1]))} for row in rows]}

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
        fallback = next((item for item in _sqlite_students() if item["id"] == student_id), None)
        if fallback:
            return fallback
        raise
    except Exception as e:
        fallback = next((item for item in _sqlite_students() if item["id"] == student_id), None)
        if fallback:
            return fallback
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
        return {"student_id": student_id, "mastery_data": _sqlite_mastery(student_id)}

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
        return {"student_id": student_id, "weak_points": _sqlite_mastery(student_id, threshold)}

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
        if not students:
            students = _sqlite_students(class_name)
        return {"class_name": class_name, "total": len(students), "data": students}
    except Exception as e:
        students = _sqlite_students(class_name)
        return {"class_name": class_name, "total": len(students), "data": students}

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
