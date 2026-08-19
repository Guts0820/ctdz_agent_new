from fastapi import APIRouter

from backend.api_gateway.services import student_statistics_service


router = APIRouter(tags=["student-statistics"])


@router.get("/api/v1/student/{student_id}/mastery")
def get_student_mastery(student_id: str) -> dict:
    return student_statistics_service.get_mastery(student_id)


@router.get("/api/class/{class_name}/mistake-stats")
def get_class_mistake_stats(class_name: str) -> dict:
    return student_statistics_service.get_class_mistake_stats(class_name)


@router.get("/api/student/{student_id}/stats")
def get_student_stats(student_id: str) -> dict:
    return student_statistics_service.get_student_stats(student_id)


@router.get("/api/student/{student_id}/wrong-answers")
def get_wrong_answers(student_id: str) -> dict:
    return student_statistics_service.get_wrong_answers(student_id)
