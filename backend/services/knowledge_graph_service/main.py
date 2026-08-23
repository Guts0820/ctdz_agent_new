from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
from backend.services.knowledge_graph_service.database import neo4j_conn
from backend.services.knowledge_graph_service.routers.knowledge_points import router as knowledge_points_router
from backend.services.knowledge_graph_service.routers.questions import router as questions_router
from backend.services.knowledge_graph_service.routers.error_causes import router as error_causes_router
from backend.services.knowledge_graph_service.routers.internal_questions import router as internal_questions_router
from backend.services.knowledge_graph_service.vector_index import ensure_vector_index

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

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
app.include_router(internal_questions_router)

@app.on_event("startup")
async def startup():
    neo4j_conn.connect()
    try:
        neo4j_conn.query(
            "CREATE CONSTRAINT question_fingerprint_unique IF NOT EXISTS "
            "FOR (q:Question) REQUIRE q.fingerprint IS UNIQUE"
        )
    except Exception as error:
        print(f"Question fingerprint constraint unavailable; upsert remains fingerprint-based: {error}")
    try:
        ensure_vector_index()
    except Exception as error:
        print(f"Vector index unavailable; lexical retrieval remains enabled: {error}")

@app.on_event("shutdown")
async def shutdown():
    neo4j_conn.close()

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
