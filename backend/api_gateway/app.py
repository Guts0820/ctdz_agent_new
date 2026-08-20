"""FastAPI application composition for the backend gateway."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api_gateway.routers import (
    error_causes,
    external_error_analysis,
    health,
    homework_batches,
    knowledge_points,
    mistake_corrections,
    questions,
    review_proxy,
    student_statistics,
    students,
    standard_answers,
    submissions,
    users,
)
# Backward-compatible imports for callers that previously imported these contracts
# from the application entry module. Route handlers remain in ``routers``.
from backend.api_gateway.models import SubmitRequest, SubmitResponse
from backend.api_gateway.services.submission_service import prepare_judging_input, process_submission


app = FastAPI(title="AI Math Error Correction System API Gateway", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for router in (
    students.router,
    knowledge_points.router,
    questions.router,
    error_causes.router,
    users.router,
    submissions.router,
    mistake_corrections.router,
    homework_batches.router,
    standard_answers.router,
    student_statistics.router,
    external_error_analysis.router,
    review_proxy.router,
    health.router,
):
    app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
