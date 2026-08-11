from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
from database import neo4j_conn
from user_database import user_db
from routers.knowledge_points import router as knowledge_points_router
from routers.questions import router as questions_router
from routers.error_causes import router as error_causes_router
from routers.users import router as users_router
from routers.students import router as students_router
from routers.growth_report import router as growth_report_router
from mastery.api import router as mastery_router
from datahub.api import router as datahub_router
from review.api.priority import router as review_priority_router
from review.api.review_plans import router as review_plans_router
from review.api.review_sessions import router as review_sessions_router
from review.api.corrections import router as review_corrections_router

load_dotenv()

app = FastAPI(
    title="小学生数学知识图谱 API",
    description="提供知识点查询、题目推荐、错因分析等功能",
    version="1.0.0",
    default_response_class=JSONResponse
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_DIR = r"D:\HuaweiMoveData\Users\jiazi\Desktop\教育知识图谱数据集收集\已收集好的数据\question\image"
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

@app.middleware("http")
async def add_encoding_header(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type and "charset" not in content_type:
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

app.include_router(knowledge_points_router)
app.include_router(questions_router)
app.include_router(error_causes_router)
app.include_router(users_router)
app.include_router(students_router)
app.include_router(growth_report_router)
app.include_router(mastery_router)
app.include_router(datahub_router)
app.include_router(review_priority_router, prefix="/api")
app.include_router(review_plans_router, prefix="/api")
app.include_router(review_sessions_router, prefix="/api")
app.include_router(review_corrections_router, prefix="/api")

@app.on_event("startup")
async def startup():
    neo4j_conn.connect()
    user_db.connect()

@app.on_event("shutdown")
async def shutdown():
    neo4j_conn.close()
    user_db.close()

@app.get("/")
def root():
    return {"message": "小学生数学知识图谱 API 服务运行中"}

@app.get("/health")
def health_check():
    try:
        result = neo4j_conn.query("MATCH (n) RETURN count(n) as total LIMIT 1")
        return {"status": "healthy", "neo4j": "connected", "node_count": result[0]["total"] if result else 0}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"数据库连接失败: {str(e)}")

@app.get("/stats")
def get_stats():
    try:
        node_stats = neo4j_conn.query("MATCH (n) RETURN labels(n) as label, count(*) as count")
        rel_stats = neo4j_conn.query("MATCH ()-[r]->() RETURN type(r) as relation_type, count(*) as count")
        
        return {
            "nodes": [{"label": str(n["label"]), "count": n["count"]} for n in node_stats],
            "relationships": [{"type": r["relation_type"], "count": r["count"]} for r in rel_stats]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host=host, port=port)