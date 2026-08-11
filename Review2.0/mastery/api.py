from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from .calculator import (
    calculate_knowledge_mastery,
    calculate_five_dimension_scores,
    calculate_class_average_mastery,
    MasteryResult,
    ExerciseRecord,
    KnowledgePoint
)
from .database import MasteryDatabase

router = APIRouter(prefix="/api/mastery", tags=["mastery"])

db = MasteryDatabase()


@router.post("/calculate")
def calculate_single_mastery(student_id: int, knowledge_id: str):
    try:
        records = db.get_student_exercise_records(student_id, knowledge_id)
        
        all_points = db.get_all_knowledge_points()
        point = next((p for p in all_points if p.knowledge_id == knowledge_id), None)
        
        if not point:
            point = KnowledgePoint(knowledge_id=knowledge_id, title=knowledge_id, importance=0.8)
        
        result = calculate_knowledge_mastery(
            knowledge_id=point.knowledge_id,
            title=point.title,
            exercise_records=records,
            importance=point.importance
        )
        
        return {
            "student_id": student_id,
            "knowledge_id": result.knowledge_id,
            "title": result.title,
            "accuracy": round(result.accuracy, 1),
            "consistency": round(result.consistency, 1),
            "retention": round(result.retention, 1),
            "error_control": round(result.error_control, 1),
            "raw_mastery": round(result.raw_mastery, 1),
            "confidence": round(result.confidence, 2),
            "final_mastery": round(result.final_mastery, 1),
            "priority": round(result.priority, 1),
            "skill_gap": round(result.skill_gap, 1),
            "forgetting_risk": round(result.forgetting_risk, 1),
            "trend": round(result.trend, 1),
            "state": result.state
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/five_dimension")
def get_five_dimension_scores(student_id: int):
    try:
        knowledge_points = db.get_student_knowledge_points(student_id)
        
        if not knowledge_points:
            knowledge_points = db.get_all_knowledge_points()[:10]
        
        mastery_results = []
        for point in knowledge_points:
            records = db.get_student_exercise_records(student_id, point.knowledge_id)
            result = calculate_knowledge_mastery(
                knowledge_id=point.knowledge_id,
                title=point.title,
                exercise_records=records,
                importance=point.importance
            )
            mastery_results.append(result)
        
        scores = calculate_five_dimension_scores(mastery_results)
        return {"student_id": student_id, "dimensions": scores}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/class_average")
def get_class_average_mastery(class_id: int):
    try:
        students = db.get_students_in_class(class_id)
        
        if not students:
            return {"class_id": class_id, "knowledge_list": []}
        
        student_mastery_results = []
        all_points = db.get_all_knowledge_points()
        
        for student_id in students:
            student_results = []
            for point in all_points[:15]:
                records = db.get_student_exercise_records(student_id, point.knowledge_id)
                result = calculate_knowledge_mastery(
                    knowledge_id=point.knowledge_id,
                    title=point.title,
                    exercise_records=records,
                    importance=point.importance
                )
                student_results.append(result)
            student_mastery_results.append(student_results)
        
        average_results = calculate_class_average_mastery(student_mastery_results)
        return {"class_id": class_id, "knowledge_list": average_results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student_overview/{student_id}")
def get_student_mastery_overview(student_id: int):
    try:
        knowledge_points = db.get_student_knowledge_points(student_id)
        
        if not knowledge_points:
            knowledge_points = db.get_all_knowledge_points()[:15]
        
        knowledge_list = []
        for point in knowledge_points:
            records = db.get_student_exercise_records(student_id, point.knowledge_id)
            result = calculate_knowledge_mastery(
                knowledge_id=point.knowledge_id,
                title=point.title,
                exercise_records=records,
                importance=point.importance
            )
            knowledge_list.append({
                "knowledge_id": result.knowledge_id,
                "title": result.title,
                "mastery_level": round(result.final_mastery, 1),
                "priority": round(result.priority, 1),
                "confidence": round(result.confidence, 2),
                "state": result.state
            })
        
        return {"student_id": student_id, "knowledge_list": knowledge_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add_record")
def add_exercise_record(
    student_id: int,
    knowledge_id: str,
    is_correct: bool,
    error_causes: Optional[List[str]] = None
):
    try:
        db.add_exercise_record(student_id, knowledge_id, is_correct, error_causes)
        return {"success": True, "message": "记录添加成功"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge_points")
def get_knowledge_points():
    try:
        points = db.get_all_knowledge_points()
        return [
            {"knowledge_id": p.knowledge_id, "title": p.title, "importance": p.importance}
            for p in points
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))