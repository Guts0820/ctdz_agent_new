"""Review 模块独立服务 (:8087)。"""

from fastapi import FastAPI

app = FastAPI(title="Review Service", version="2.0.0")

try:
    from backend.services.review_service.review.api import review_sessions, review_plans, corrections, priority
    from backend.services.review_service.datahub.api import router as datahub_router
    from backend.services.review_service.mastery.api import router as mastery_router
    app.include_router(review_plans.router)
    app.include_router(review_sessions.router)
    app.include_router(corrections.router)
    app.include_router(priority.router)
    app.include_router(mastery_router)
    app.include_router(datahub_router)
    print("[Review Service] 路由挂载成功")
except Exception as e:
    print(f"[Review Service] 路由挂载失败: {e}")
    raise


@app.get("/health")
def health():
    return {"status": "healthy", "service": "Review Service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8087)
