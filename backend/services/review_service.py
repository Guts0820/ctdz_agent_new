"""Review 模块独立服务 (:8087)——挂载 Review 2.0 全部 API 路由"""
import sys
import os

# 确保 review 模块可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend_v2', 'theirs'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI

app = FastAPI(title="Review Service", version="2.0.0")

try:
    from review.api import review_sessions, review_plans, corrections, priority
    app.include_router(review_plans.router)
    app.include_router(review_sessions.router)
    app.include_router(corrections.router)
    app.include_router(priority.router)
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
