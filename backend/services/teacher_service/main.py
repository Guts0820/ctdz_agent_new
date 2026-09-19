"""教师端业务服务入口。"""

from fastapi import Depends, FastAPI

from backend.services.teacher_service.routers.homework_batches import router as homework_batches_router
from backend.services.teacher_service.routers.standard_answers import router as standard_answers_router
from backend.services.teacher_service.routers.question_imports import router as question_imports_router
from backend.services.teacher_service.routers.questions import router as questions_router

from backend.shared.config import SERVICE_BIND_HOST
from backend.shared.internal_auth import require_internal_token

app = FastAPI(dependencies=[Depends(require_internal_token)], title="Teacher Service", version="1.0.0")
app.include_router(homework_batches_router)
app.include_router(standard_answers_router)
app.include_router(question_imports_router)
app.include_router(questions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "teacher"}


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host=SERVICE_BIND_HOST, port=int(os.getenv("API_PORT", "8090")))
