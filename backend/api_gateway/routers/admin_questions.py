from fastapi import APIRouter, Header, Query

from backend.api_gateway.services.admin_question_client import request_admin_questions

router = APIRouter(prefix="/api/v1/admin/questions", tags=["admin-question-bank"])


@router.get("")
def list_questions(status: str | None = Query(None), x_role: str | None = Header(None), x_actor: str | None = Header(None)):
    path = "/internal/api/v1/admin/questions" + (f"?status={status}" if status else "")
    return request_admin_questions("GET", path, role=x_role, actor=x_actor)


@router.post("/{question_id}/review")
def review_question(question_id: str, payload: dict, x_role: str | None = Header(None), x_actor: str | None = Header(None)):
    return request_admin_questions("POST", f"/internal/api/v1/admin/questions/{question_id}/review", payload, x_role, x_actor)


@router.post("/{question_id}/merge")
def merge_question(question_id: str, payload: dict, x_role: str | None = Header(None), x_actor: str | None = Header(None)):
    return request_admin_questions("POST", f"/internal/api/v1/admin/questions/{question_id}/merge", payload, x_role, x_actor)


@router.get("/audit/logs")
def audit_logs(limit: int = Query(100, ge=1, le=500), x_role: str | None = Header(None)):
    return request_admin_questions("GET", f"/internal/api/v1/admin/questions/audit/logs?limit={limit}", role=x_role)
