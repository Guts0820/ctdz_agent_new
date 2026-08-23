"""管理员题库审核、重复合并和审计接口。"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.shared.config import DATABASE_PATH

router = APIRouter(prefix="/internal/api/v1/admin/questions", tags=["admin-question-bank"])


class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(pending|processing|ready|failed)$")
    reason: str = ""


class MergeRequest(BaseModel):
    duplicate_ids: list[str] = Field(min_length=1)
    reason: str = ""


def _require_admin(x_role: str | None) -> None:
    if (x_role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作统一题库")


def _audit(action: str, actor: str | None, target_id: str, detail: dict[str, Any]) -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS question_audit_log "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, actor TEXT, target_id TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO question_audit_log(action, actor, target_id, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (action, actor, target_id, json.dumps(detail, ensure_ascii=False), datetime.now().isoformat()),
        )
        connection.commit()


@router.get("")
def list_question_review_queue(status: str | None = Query(None), x_role: str | None = Header(None), x_actor: str | None = Header(None)) -> dict[str, Any]:
    _require_admin(x_role)
    where = "WHERE q.status = $status" if status else ""
    rows = neo4j_conn.query(
        f"MATCH (q:Question) {where} RETURN q ORDER BY q.updated_at DESC",
        {"status": status} if status else {},
    )
    data = [dict(row.get("q", {})) for row in rows]
    _audit("list", x_actor, "question-bank", {"status": status, "count": len(data)})
    return {"data": data, "total": len(data)}


@router.post("/{question_id}/review")
def review_question(question_id: str, request: ReviewRequest, x_role: str | None = Header(None), x_actor: str | None = Header(None)) -> dict[str, Any]:
    _require_admin(x_role)
    rows = neo4j_conn.query("MATCH (q:Question {id: $id}) RETURN q", {"id": question_id})
    if not rows:
        raise HTTPException(status_code=404, detail=f"题目不存在: {question_id}")
    neo4j_conn.query(
        "MATCH (q:Question {id: $id}) SET q.status = $status, "
        "q.standard_solution_status = CASE WHEN $status = 'ready' THEN 'ready' ELSE q.standard_solution_status END, "
        "q.review_reason = $reason, q.reviewed_at = datetime() RETURN q",
        {"id": question_id, "status": request.status, "reason": request.reason},
    )
    _audit("review", x_actor, question_id, request.model_dump())
    return {"status": "success", "question_id": question_id, "question_status": request.status}


@router.post("/{question_id}/merge")
def merge_questions(question_id: str, request: MergeRequest, x_role: str | None = Header(None), x_actor: str | None = Header(None)) -> dict[str, Any]:
    _require_admin(x_role)
    duplicate_ids = list(dict.fromkeys(item for item in request.duplicate_ids if item and item != question_id))
    if not duplicate_ids:
        raise HTTPException(status_code=422, detail="至少指定一个不同的重复题目")
    rows = neo4j_conn.query(
        "MATCH (canonical:Question {id: $canonical}) "
        "OPTIONAL MATCH (duplicate:Question) WHERE duplicate.id IN $duplicates "
        "RETURN canonical, collect(duplicate) AS duplicates",
        {"canonical": question_id, "duplicates": duplicate_ids},
    )
    if not rows or not rows[0].get("canonical"):
        raise HTTPException(status_code=404, detail=f"标准题目不存在: {question_id}")
    found = [item for item in rows[0].get("duplicates", []) if item]
    if len(found) != len(duplicate_ids):
        raise HTTPException(status_code=404, detail="部分重复题目不存在")
    neo4j_conn.query(
        "MATCH (canonical:Question {id: $canonical}) "
        "MATCH (duplicate:Question) WHERE duplicate.id IN $duplicates "
        "SET canonical.aliases = coalesce(canonical.aliases, []) + [duplicate.text] "
        "SET duplicate.merged_into = canonical.id, duplicate.status = 'merged' "
        "RETURN canonical",
        {"canonical": question_id, "duplicates": duplicate_ids},
    )
    _audit("merge", x_actor, question_id, {"duplicate_ids": duplicate_ids, "reason": request.reason})
    return {"status": "success", "canonical_id": question_id, "merged_count": len(duplicate_ids)}


@router.get("/audit/logs")
def audit_logs(limit: int = Query(100, ge=1, le=500), x_role: str | None = Header(None)) -> dict[str, Any]:
    _require_admin(x_role)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM question_audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"data": [dict(row) for row in rows], "total": len(rows)}
