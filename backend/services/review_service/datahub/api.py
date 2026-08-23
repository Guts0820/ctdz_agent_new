from fastapi import APIRouter, HTTPException
from typing import List, Dict
from .models import (
    LearningPathNode,
    StatisticsOverview,
    ClassMasteryData,
    RevisionStatistics,
    GrowthReportData
)
from .core.learning_path import LearningPathRecommender
from .core.statistics import StatisticsReporter
from .core.aggregator import DataAggregator
from .clients.review_plan_client import ReviewPlanClient
from .clients.error_analysis_client import ErrorAnalysisClient

router = APIRouter(prefix="/api/datahub", tags=["datahub"])

path_recommender = LearningPathRecommender()
statistics = StatisticsReporter()
aggregator = DataAggregator()
review_plan_client = ReviewPlanClient()
error_analysis_client = ErrorAnalysisClient()


@router.get("/growth_report/{student_id}", response_model=GrowthReportData)
def get_growth_report(student_id: str):
    try:
        return aggregator.generate_growth_report(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning_path/{student_id}")
def get_learning_path(student_id: str, limit: int = 5):
    try:
        path = path_recommender.generate_path(student_id, limit)
        return {"student_id": student_id, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/overview", response_model=StatisticsOverview)
def get_statistics_overview():
    try:
        return statistics.get_system_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/class_mastery/{class_id}")
def get_class_mastery(class_id: int):
    try:
        result = statistics.get_class_mastery(class_id)
        return {"class_id": class_id, "knowledge_list": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/revision", response_model=RevisionStatistics)
def get_revision_statistics():
    try:
        return statistics.get_revision_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/review_plan")
def get_review_plan_statistics():
    try:
        return statistics.get_review_plan_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/grade_distribution")
def get_grade_distribution():
    try:
        return statistics.get_grade_distribution()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review_plan/generate")
def generate_review_plan(student_id: int):
    try:
        plan = review_plan_client.generate_review_plan(student_id)
        return {"student_id": student_id, "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/error/analyze")
def analyze_error(student_id: int, question_id: str, 
                  student_answer: str, correct_answer: str):
    try:
        result = error_analysis_client.analyze_error(
            student_id, question_id, student_answer, correct_answer
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/error/high_frequency")
def get_high_frequency_wrong(class_id: int, limit: int = 5):
    try:
        result = error_analysis_client.get_high_frequency_wrong(class_id, limit)
        return {"class_id": class_id, "wrong_questions": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning_path/{student_id}/detailed")
def get_detailed_learning_path(student_id: str, limit: int = 5):
    try:
        return path_recommender.generate_detailed_path(student_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{knowledge_id}")
def get_knowledge_detail(knowledge_id: str):
    try:
        result = path_recommender.get_knowledge_detail(knowledge_id)
        if not result:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mistake_analysis/{student_id}")
def get_mistake_analysis(student_id: str):
    try:
        return path_recommender.get_mistake_analysis(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comprehensive/{student_id}")
def get_comprehensive_analysis(student_id: str):
    try:
        return aggregator.get_comprehensive_analysis(student_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{knowledge_id}/questions")
def get_knowledge_questions(knowledge_id: str, difficulty: int = 0, limit: int = 10):
    try:
        questions = path_recommender._get_questions_for_knowledge(knowledge_id, difficulty, limit)
        return {"knowledge_id": knowledge_id, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{knowledge_id}/mistakes")
def get_knowledge_mistakes(knowledge_id: str, student_id: int = 0):
    try:
        mistakes = path_recommender._get_mistakes_for_knowledge(knowledge_id, student_id)
        error_analysis = path_recommender._get_error_causes_for_knowledge(knowledge_id)
        error_categories = path_recommender._get_error_categories_for_knowledge(knowledge_id)
        return {
            "knowledge_id": knowledge_id,
            "mistakes": mistakes,
            "error_analysis": error_analysis,
            "error_categories": error_categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
