from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import requests
from backend.shared.config import REVIEW_SERVICE_URL

app = FastAPI(title="State Service", version="1.0.0")

DATABASE = "database/sqlite/example_db.db"

class StateUpdateRequest(BaseModel):
    student_id: str
    knowledge_id: str
    is_correct: bool
    confidence: float
    mistake_case_id: Optional[str] = None
    answer_history_id: Optional[str] = None

class StateUpdateResponse(BaseModel):
    master_level: float
    next_action: str
    correct_count: int
    wrong_count: int
    mastery_status: str
    knowledge_mastery_id: str
    should_generate_review: bool
    mastery: float
    priority: float
    components: dict
    mastery_components: dict
    formula_version: str

class ReviewGenerateRequest(BaseModel):
    student_id: str
    knowledge_id: str
    knowledge_mastery_id: str
    master_level: float

class ReviewGenerateResponse(BaseModel):
    review_plan_id: str
    review_stages: list
    stage_dates: dict
    status: str
    push_records: list

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/internal/api/v1/state/update", response_model=StateUpdateResponse)
def update_state(request: StateUpdateRequest):
    response = requests.post(
        f"{REVIEW_SERVICE_URL}/priority-runs/internal/mastery-update",
        json=request.model_dump(),
        timeout=30,
    )
    response.raise_for_status()
    return StateUpdateResponse(**response.json())

@app.post("/internal/api/v1/state/generate-review", response_model=ReviewGenerateResponse)
def generate_review(request: ReviewGenerateRequest):
    response = requests.post(
        f"{REVIEW_SERVICE_URL}/review-plans",
        json={"student_id": request.student_id, "mode": "question_count", "question_count": 10},
        timeout=30,
    )
    response.raise_for_status()
    plan = response.json()
    return ReviewGenerateResponse(
        review_plan_id=plan["id"], review_stages=["daily"],
        stage_dates={"daily": plan["business_date"]}, status=plan["status"],
        push_records=plan.get("items", []),
    )

@app.get("/internal/api/v1/state/mastery/{student_id}")
def get_mastery(student_id: str, knowledge_id: Optional[str] = None):
    with get_db() as conn:
        cursor = conn.cursor()
        
        if knowledge_id:
            cursor.execute('''
                SELECT km.*, k.knowledge_scope
                FROM knowledge_mastery km
                LEFT JOIN knowledge k ON km.knowledge_id = k.knowledge_id
                WHERE km.student_id = ? AND km.knowledge_id = ?
            ''', (student_id, knowledge_id))
            rows = [dict(row) for row in cursor.fetchall()]
        else:
            cursor.execute('''
                SELECT km.*, k.knowledge_scope
                FROM knowledge_mastery km
                LEFT JOIN knowledge k ON km.knowledge_id = k.knowledge_id
                WHERE km.student_id = ?
            ''', (student_id,))
            rows = [dict(row) for row in cursor.fetchall()]
        
        return {"status": "success", "data": rows}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "State Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
