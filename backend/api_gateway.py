import json
import sys
from datetime import datetime
from typing import Optional
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("错误：无法导入 fastapi。请运行 'pip install fastapi' 安装依赖。", file=sys.stderr)
    sys.exit(1)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import sqlite3
import os as _os
sys.path.insert(0, 'backend/services')
from id_utils import generate_id

# 晓琳团队路由模块
sys.path.insert(0, 'backend')
from routers import students, knowledge_points, questions, error_causes, users

app = FastAPI(title="AI Math Error Correction System API Gateway", version="1.0.0")

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载晓琳团队的路由
app.include_router(students.router)
app.include_router(knowledge_points.router)
app.include_router(questions.router)
app.include_router(error_causes.router)
app.include_router(users.router)

SERVICE_URLS = {
    "analysis": "http://127.0.0.1:8081",
    "error_analysis": "http://127.0.0.1:8082",
    "knowledge": "http://127.0.0.1:8083",
    "teaching": "http://127.0.0.1:8084",
    "state": "http://127.0.0.1:8085",
    "review": "http://127.0.0.1:8087",
    "knowledge_graph": "http://127.0.0.1:8007"
}

# Review API 路由代理转发
REVIEW_PROXY_PATHS = [
    "/api/review-plans", "/api/review-sessions", "/api/attempts", "/api/priority-runs"
]

DATABASE = "backend/database/example_db.db"
KG_SERVICE_URL = "http://127.0.0.1:8007"

class ExternalErrorAnalyzeRequest(BaseModel):
    student_id: int
    question_id: str
    student_answer: str
    correct_answer: str

# 批次管理相关模型
class CreateBatchRequest(BaseModel):
    class_id: str
    teacher_id: str
    batch_date: str  # 格式: YYYY-MM-DD
    question_ids: list[str]

class BatchResponse(BaseModel):
    batch_id: str
    class_id: str
    teacher_id: str
    batch_date: str
    release_status: str
    question_count: int

class ReleasePartialRequest(BaseModel):
    question_ids: list[str]

class SubmitRequest(BaseModel):
    student_id: str
    question_id: Optional[str] = None
    image: Optional[str] = None
    original_question: Optional[str] = None
    student_write: Optional[str] = None
    grade: Optional[str] = "三年级"

class SubmitResponse(BaseModel):
    status: str
    data: dict

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def lookup_knowledge_id(question_id: Optional[str]) -> Optional[str]:
    if not question_id:
        return None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT knowledge_id FROM question_knowledge_mapping WHERE question_id = ?
        ''', (question_id,))
        row = cursor.fetchone()
        if row:
            return row["knowledge_id"]

    return None

def _lookup_question_text(question_id: str) -> Optional[str]:
    """从数据库查题目文本，查不到则试 KG Service。"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT question_description FROM question WHERE question_id = ?", (question_id,))
        row = cursor.fetchone()
        if row and row["question_description"]:
            return row["question_description"]

    try:
        r = requests.get(f"{SERVICE_URLS['knowledge_graph']}/api/questions/{question_id}", timeout=5)
        if r.ok:
            data = r.json()
            return data.get("text") or data.get("prompt") or data.get("question_description")
    except Exception:
        pass
    return None

def is_answer_released(question_id: str) -> bool:
    """
    判断某道题的答案能否返回给学生

    Args:
        question_id: 题目ID

    Returns:
        True: 可以返回答案（已发布或不属于任何受控批次）
        False: 不能返回答案（锁定状态）
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # 查询题目所属的最新批次及其发布状态
        cursor.execute('''
            SELECT hb.release_status
            FROM homework_batch_question hbq
            JOIN homework_batch hb ON hbq.batch_id = hb.batch_id
            WHERE hbq.question_id = ?
            ORDER BY hb.created_at DESC LIMIT 1
        ''', (question_id,))
        row = cursor.fetchone()

        # 如果这道题不属于任何受控批次，默认不限制（兼容旧逻辑）
        if not row:
            return True

        # 已发布：可以返回答案
        if row["release_status"] == "released":
            return True

        # 部分发布：检查是否有单独放行记录
        if row["release_status"] == "partial":
            cursor.execute('''
                SELECT 1 FROM question_release_override
                WHERE question_id = ?
            ''', (question_id,))
            return cursor.fetchone() is not None

        # locked 状态：不能返回答案
        return False

@app.post("/api/v1/submit", response_model=SubmitResponse)
def submit_homework(request: SubmitRequest):
    try:
        analysis_result = call_analysis_service(request)

        # OCR 数据透传（来自 Analysis Service 的真实 OCR 或模拟 OCR）
        ocr_data = {}
        if analysis_result.get("ocr_markdown") is not None:
            ocr_data["ocr"] = {
                "markdown": analysis_result.get("ocr_markdown"),
                "engine": analysis_result.get("ocr_engine"),
                "fallback_used": analysis_result.get("ocr_fallback_used"),
                "status": analysis_result.get("ocr_status"),
            }

        if analysis_result["is_copy"]:
            guide_result = call_teaching_guide(analysis_result)
            return SubmitResponse(
                status="success",
                data={
                    "judge_result": analysis_result["judge_result"],
                    "is_copy": True,
                    "hints": guide_result.get("hints", []),
                    "explanation": "检测到疑似抄袭，请完成引导问题后重新提交",
                    "next_action": "guide",
                    **ocr_data,
                }
            )
        
        question_id = request.question_id or analysis_result.get("question_id")
        knowledge_id = lookup_knowledge_id(question_id)
        
        if analysis_result["judge_result"] == "correct":
            if not knowledge_id:
                return SubmitResponse(
                    status="success",
                    data={
                        "judge_result": "correct",
                        "step_feedback": analysis_result["step_feedback"],
                        "master_level": 1.0,
                        "next_action": "guide",
                        "warning": "无法确定题目对应的知识点，跳过状态更新",
                        **ocr_data,
                    }
                )
            
            state_result = call_state_service(request.student_id, knowledge_id, True, analysis_result["confidence"])
            return SubmitResponse(
                status="success",
                data={
                    "judge_result": "correct",
                    "step_feedback": analysis_result["step_feedback"],
                    "knowledge_id": knowledge_id,
                    "master_level": state_result["master_level"],
                    "next_action": state_result["next_action"],
                    **ocr_data,
                }
            )
        
        error_analysis_result = call_error_analysis_service(analysis_result)
        
        if not knowledge_id:
            knowledge_id = error_analysis_result.get("knowledge_id", "G-N-1-001")
        
        knowledge_result = call_knowledge_service({"knowledge_id": knowledge_id, "knowledge_scope": error_analysis_result.get("knowledge_scope", "")})
        
        frequency_result = call_frequency_check(request.student_id, knowledge_id)
        
        if not frequency_result["push_permission"]:
            state_result = call_state_service(request.student_id, knowledge_id, False, error_analysis_result["total_confidence"])
            
            return SubmitResponse(
                status="success",
                data={
                    "judge_result": analysis_result["judge_result"],
                    "step_feedback": analysis_result["step_feedback"],
                    "error_tags": error_analysis_result["error_tags"],
                    "knowledge_scope": error_analysis_result["knowledge_scope"],
                    "explanation": knowledge_result["knowledge_explanation"],
                    "master_level": state_result["master_level"],
                    "next_action": "frequency_limit_exceeded",
                    "frequency_info": frequency_result,
                    **ocr_data,
                }
            )
        
        state_before = call_state_service(request.student_id, knowledge_id, False, error_analysis_result["total_confidence"])

        teaching_result = call_teaching_service(error_analysis_result, state_before["master_level"], analysis_result)

        if state_before["should_generate_review"]:
            review_result = call_generate_review(request.student_id, knowledge_id, state_before["knowledge_mastery_id"], state_before["master_level"])
        else:
            review_result = None

        # 组装返回数据
        response_data = {
            "judge_result": analysis_result["judge_result"],
            "step_feedback": analysis_result["step_feedback"],
            "error_step_list": analysis_result["error_step_list"],
            "miss_step_list": analysis_result["miss_step_list"],
            "is_copy": analysis_result["is_copy"],
            "core_error_type": analysis_result["core_error_type"],
            "confidence": analysis_result["confidence"],
            "error_tags": error_analysis_result["error_tags"],
            "knowledge_id": knowledge_id,
            "knowledge_scope": error_analysis_result["knowledge_scope"],
            "knowledge_explanation": knowledge_result["knowledge_explanation"],
            "difficulty": knowledge_result["difficulty"],
            "standard_solution": knowledge_result["standard_solution"],
            "explanation": teaching_result["explanation"],
            "guided_explanation": teaching_result.get("guided_explanation", ""),
            "final_answer_explanation": teaching_result.get("final_answer_explanation", ""),
            "hints": teaching_result["hints"],
            "practice_list": teaching_result["practice_list"],
            "teaching_mode": teaching_result["teaching_mode"],
            "master_level": state_before["master_level"],
            "next_action": state_before["next_action"],
            "correct_count": state_before["correct_count"],
            "wrong_count": state_before["wrong_count"],
            "mastery_status": state_before["mastery_status"],
            "review_plan": review_result
        }

        # OCR 数据透传
        response_data.update(ocr_data)

        # 答案权限过滤：如果题目答案未发布，隐藏完整答案讲解
        if question_id and not is_answer_released(question_id):
            response_data["final_answer_explanation"] = None
            response_data["explanation"] = teaching_result.get("guided_explanation", "")
            response_data["answer_released"] = False
        else:
            response_data["answer_released"] = True

        return SubmitResponse(status="success", data=response_data)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def call_analysis_service(request: SubmitRequest) -> dict:
    url = f"{SERVICE_URLS['analysis']}/internal/api/v1/analysis/process"

    # 补全题目文本：新 Analysis Service 要求 image 或 original_question 至少一个非空
    original_question = request.original_question
    if not original_question and request.question_id:
        original_question = _lookup_question_text(request.question_id)

    payload = {
        "student_id": request.student_id,
        "question_id": request.question_id,
        "image": request.image,
        "original_question": original_question,
        "student_write": request.student_write,
        "text_status": "normal"
    }
    # OCR 首次推理可能较久，使用长超时
    response = requests.post(url, json=payload, timeout=600)
    response.raise_for_status()
    return response.json()

def call_error_analysis_service(analysis_result: dict) -> dict:
    url = f"{SERVICE_URLS['error_analysis']}/internal/api/v1/error-analysis/analyze"
    payload = {
        "student_id": analysis_result.get("student_id", ""),
        "question_id": analysis_result.get("question_id"),
        "original_question": analysis_result["original_question"],
        "student_write": analysis_result["student_write"],
        "judge_result": analysis_result["judge_result"],
        "core_error_type": analysis_result["core_error_type"],
        "step_feedback": analysis_result["step_feedback"],
        "error_step_list": analysis_result["error_step_list"],
        "miss_step_list": analysis_result["miss_step_list"],
        "confidence": analysis_result["confidence"]
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def call_knowledge_service(error_analysis_result: dict) -> dict:
    url = f"{SERVICE_URLS['knowledge']}/internal/api/v1/knowledge/retrieve"
    payload = {
        "knowledge_id": error_analysis_result["knowledge_id"],
        "knowledge_scope": error_analysis_result["knowledge_scope"],
        "textbook_version": "人教版"
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        # KG Service 找不到时用 SQLite 本地兜底
        kid = error_analysis_result.get("knowledge_id", "")
        scope = error_analysis_result.get("knowledge_scope", "")
        return {
            "knowledge_explanation": scope or kid,
            "difficulty": "medium",
            "standard_solution": "",
            "scope_validation": True,
            "prerequisite": "",
            "next_knowledge": "",
            "textbook_version": "人教版",
            "unit": "",
            "common_errors": "",
            "forbidden_explanation": "",
            "example": "",
            "teaching_tips": "",
        }

def call_teaching_service(error_analysis_result: dict, master_level: float, analysis_result: dict) -> dict:
    url = f"{SERVICE_URLS['teaching']}/internal/api/v1/teaching/generate"
    payload = {
        "error_tags": error_analysis_result["error_tags"],
        "knowledge_scope": error_analysis_result["knowledge_scope"],
        "knowledge_id": error_analysis_result.get("knowledge_id"),
        "master_level": master_level,
        "original_question": analysis_result["original_question"],
        "student_write": analysis_result["student_write"],
        "difficulty": "medium",
        "grade": "三年级"
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def call_state_service(student_id: str, knowledge_id: str, is_correct: bool, confidence: float) -> dict:
    url = f"{SERVICE_URLS['state']}/internal/api/v1/state/update"
    payload = {
        "student_id": student_id,
        "knowledge_id": knowledge_id,
        "is_correct": is_correct,
        "confidence": confidence
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def call_frequency_check(student_id: str, knowledge_id: str) -> dict:
    url = f"{SERVICE_URLS['teaching']}/internal/api/v1/teaching/frequency-check"
    payload = {
        "student_id": student_id,
        "knowledge_id": knowledge_id,
        "current_time": datetime.now().isoformat()
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def call_generate_review(student_id: str, knowledge_id: str, knowledge_mastery_id: str, master_level: float) -> dict:
    url = f"{SERVICE_URLS['state']}/internal/api/v1/state/generate-review"
    payload = {
        "student_id": student_id,
        "knowledge_id": knowledge_id,
        "knowledge_mastery_id": knowledge_mastery_id,
        "master_level": master_level
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

def call_teaching_guide(analysis_result: dict) -> dict:
    url = f"{SERVICE_URLS['teaching']}/internal/api/v1/teaching/generate"
    payload = {
        "error_tags": [],
        "knowledge_scope": "引导模式",
        "master_level": 0.9,
        "original_question": analysis_result["original_question"],
        "student_write": analysis_result["student_write"]
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()

@app.get("/api/v1/student/{student_id}/mastery")
def get_student_mastery(student_id: str):
    url = f"{SERVICE_URLS['state']}/internal/api/v1/state/mastery/{student_id}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def fetch_question_detail(question_id: str) -> dict:
    try:
        url = f"{KG_SERVICE_URL}/api/questions/{question_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.question_id, q.question_description, q.standard_solve_steps,
                       q.answer, q.difficulty, q.grade, qk.knowledge_id
                FROM question q
                LEFT JOIN question_knowledge_mapping qk ON q.question_id = qk.question_id
                WHERE q.question_id = ?
            ''', (question_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["question_id"],
                    "text": row["question_description"] or "",
                    "answer_steps": row["standard_solve_steps"] or "",
                    "answer": row["answer"] or "",
                    "difficulty": row["difficulty"] or "medium",
                    "grade": row["grade"] or "三年级",
                    "knowledge_id": row["knowledge_id"] or ""
                }
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")

@app.post("/api/error/analyze")
def external_error_analyze(request: ExternalErrorAnalyzeRequest):
    try:
        question_detail = fetch_question_detail(request.question_id)
    except HTTPException as e:
        return {
            "error": "question_not_found",
            "message": str(e.detail),
            "question_id": request.question_id
        }
    except Exception as e:
        return {
            "error": "kg_service_unavailable",
            "message": f"知识图谱服务暂时不可用: {str(e)}",
            "fallback": "请稍后重试或联系管理员"
        }
    
    payload = {
        "student_id": f"U-{request.student_id}",
        "original_question": question_detail.get("text", ""),
        "standard_solve_steps": question_detail.get("answer_steps", ""),
        "correct_answer": request.correct_answer,
        "student_write": request.student_answer,
        "knowledge_id": question_detail.get("knowledge_id", "")
    }
    
    try:
        result = requests.post(
            f"{SERVICE_URLS['error_analysis']}/internal/api/v1/error-analysis/analyze-light",
            json=payload, timeout=30
        )
        result.raise_for_status()
        analysis_data = result.json()
    except requests.exceptions.RequestException as e:
        return {
            "error": "analysis_service_unavailable",
            "message": f"错因分析服务暂时不可用: {str(e)}",
            "question_id": request.question_id
        }
    
    error_tags = analysis_data.get("error_tags", [])
    primary_tag = error_tags[0] if error_tags else {}
    
    return {
        "error_type": primary_tag.get("error_id", "unknown"),
        "error_type_label": primary_tag.get("level3", "未知"),
        "error_detail": analysis_data.get("reasoning_content", ""),
        "related_knowledge": [analysis_data.get("knowledge_scope", "")] if analysis_data.get("knowledge_scope") else [],
        "confidence": analysis_data.get("total_confidence", 0.0),
        "all_error_tags": [
            {
                "error_id": t.get("error_id"),
                "level1": t.get("level1"),
                "level2": t.get("level2"),
                "level3": t.get("level3"),
                "confidence": t.get("confidence")
            }
            for t in error_tags
        ],
        "knowledge_id": analysis_data.get("knowledge_id", ""),
        "source": "light_analysis",
        "note": "本接口为轻量分析模式，仅基于最终答案推断，置信度相对保守"
    }

# ==================== 老师端批次管理接口 ====================

@app.post("/api/v1/teacher/homework_batch", response_model=BatchResponse)
def create_homework_batch(request: CreateBatchRequest):
    """
    创建作业批次

    Args:
        request: class_id, teacher_id, batch_date, question_ids

    Returns:
        BatchResponse: 批次信息
    """
    batch_id = generate_id("HB")

    with get_db() as conn:
        cursor = conn.cursor()

        # 创建批次记录
        cursor.execute('''
            INSERT INTO homework_batch (batch_id, class_id, teacher_id, batch_date, release_status, created_at)
            VALUES (?, ?, ?, ?, 'locked', ?)
        ''', (batch_id, request.class_id, request.teacher_id, request.batch_date, datetime.now().isoformat()))

        # 批量插入批次-题目关联
        for qid in request.question_ids:
            cursor.execute('''
                INSERT INTO homework_batch_question (batch_id, question_id)
                VALUES (?, ?)
            ''', (batch_id, qid))

        conn.commit()

    return BatchResponse(
        batch_id=batch_id,
        class_id=request.class_id,
        teacher_id=request.teacher_id,
        batch_date=request.batch_date,
        release_status="locked",
        question_count=len(request.question_ids)
    )

@app.post("/api/v1/teacher/homework_batch/{batch_id}/release")
def release_batch(batch_id: str):
    """
    一键放行整批作业

    Args:
        batch_id: 批次ID

    Returns:
        成功信息
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 检查批次是否存在
        cursor.execute('SELECT batch_id FROM homework_batch WHERE batch_id = ?', (batch_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")

        # 更新批次状态为已发布
        cursor.execute('''
            UPDATE homework_batch
            SET release_status = 'released', release_time = ?
            WHERE batch_id = ?
        ''', (datetime.now().isoformat(), batch_id))

        conn.commit()

    return {"status": "success", "message": f"批次 {batch_id} 已全部放行", "release_status": "released"}

@app.post("/api/v1/teacher/homework_batch/{batch_id}/release_partial")
def release_batch_partial(batch_id: str, request: ReleasePartialRequest):
    """
    精细放行部分题目

    Args:
        batch_id: 批次ID
        request: question_ids 要放行的题目列表

    Returns:
        成功信息和放行题目数量
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 检查批次是否存在
        cursor.execute('SELECT batch_id FROM homework_batch WHERE batch_id = ?', (batch_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")

        # 批量插入题目放行记录
        for qid in request.question_ids:
            cursor.execute('''
                INSERT OR IGNORE INTO question_release_override (batch_id, question_id, released_at)
                VALUES (?, ?, ?)
            ''', (batch_id, qid, datetime.now().isoformat()))

        # 更新批次状态为部分发布
        cursor.execute('''
            UPDATE homework_batch
            SET release_status = 'partial', release_time = ?
            WHERE batch_id = ?
        ''', (datetime.now().isoformat(), batch_id))

        conn.commit()

    return {
        "status": "success",
        "message": f"已放行 {len(request.question_ids)} 道题目",
        "release_status": "partial",
        "released_count": len(request.question_ids)
    }

# === Review API 代理转发 ===
# 以 /api/review-*, /api/attempts, /api/priority-runs 开头的请求转发到 Review Service (:8087)

@app.api_route("/api/review-plans", methods=["GET", "POST"])
async def proxy_review_plans_root(request: Request):
    return await _proxy_to_review("review-plans", "", request)

@app.api_route("/api/review-plans/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_review_plans(path: str, request: Request):
    return await _proxy_to_review("review-plans", path, request)

@app.api_route("/api/review-sessions/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_review_sessions(path: str, request: Request):
    return await _proxy_to_review("review-sessions", path, request)

@app.api_route("/api/attempts/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_attempts(path: str, request: Request):
    return await _proxy_to_review("attempts", path, request)

@app.api_route("/api/priority-runs", methods=["GET", "POST"])
async def proxy_priority_runs(request: Request):
    return await _proxy_to_review("priority-runs", "", request)

@app.api_route("/api/priority-runs/{path:path}", methods=["GET", "POST"])
async def proxy_priority_runs_path(path: str, request: Request):
    return await _proxy_to_review("priority-runs", path, request)

async def _proxy_to_review(prefix: str, path: str, request: Request):
    """将请求转发到 Review Service"""
    base = SERVICE_URLS["review"]
    target_path = f"/{prefix}"
    if path:
        target_path += f"/{path}"
    url = f"{base}{target_path}"

    body = None
    if request.method in ("POST", "PATCH", "PUT"):
        body = await request.body()

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers={"Content-Type": "application/json"},
            data=body,
            timeout=60,
        )
        try:
            content = resp.json() if resp.text else {}
        except Exception:
            content = {"detail": resp.text[:500]}
        return JSONResponse(content=content, status_code=resp.status_code)
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Review Service 不可用")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"代理请求失败: {str(e)}")


@app.get("/api/class/{class_name}/mistake-stats")
def get_class_mistake_stats(class_name: str):
    """按知识点聚合班级高频错题，取 top 5"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT qkm.knowledge_id, COUNT(*) as error_count,
                      GROUP_CONCAT(DISTINCT ah.core_error_type) as error_types
               FROM answer_history ah
               JOIN question_knowledge_mapping qkm ON ah.question_id = qkm.question_id
               WHERE ah.is_correct = 0
               GROUP BY qkm.knowledge_id
               ORDER BY error_count DESC LIMIT 5"""
        )
        rows = cursor.fetchall()
        return {
            "class_name": class_name,
            "data": [
                {
                    "knowledge_id": r["knowledge_id"],
                    "error_count": r["error_count"],
                    "error_types": (r["error_types"] or "").split(","),
                }
                for r in rows
            ],
        }


@app.get("/api/student/{student_id}/stats")
def get_student_stats(student_id: str):
    """学生首页统计数据（来自 answer_history）"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total FROM answer_history WHERE student_id = ?",
            (student_id,),
        )
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT COUNT(*) as correct FROM answer_history WHERE student_id = ? AND is_correct = 1",
            (student_id,),
        )
        correct = cursor.fetchone()["correct"]
        cursor.execute(
            "SELECT COUNT(*) as wrong FROM answer_history WHERE student_id = ? AND is_correct = 0",
            (student_id,),
        )
        wrong = cursor.fetchone()["wrong"]
        # 已复习 = 有订正记录的
        cursor.execute(
            """SELECT COUNT(*) as reviewed FROM review2_attempt
               WHERE student_answer IS NOT NULL AND correction_is_correct IS NOT NULL""",
        )
        reviewed = cursor.fetchone()["reviewed"]
        return {
            "total_questions": total,
            "correct_rate": round(correct / total * 100) if total > 0 else 0,
            "total_mistakes": wrong,
            "reviewed_mistakes": reviewed,
        }


@app.get("/api/student/{student_id}/wrong-answers")
def get_wrong_answers(student_id: str):
    """从 answer_history 读取学生错题记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT ah.answer_history_id, ah.question_id, ah.student_ocr_answer,
                      ah.judge_result, ah.core_error_type, ah.submitted_at,
                      q.question_description
               FROM answer_history ah
               LEFT JOIN question q ON ah.question_id = q.question_id
               WHERE ah.student_id = ? AND ah.is_correct = 0
               ORDER BY ah.submitted_at DESC""",
            (student_id,),
        )
        rows = cursor.fetchall()
        return {
            "student_id": student_id,
            "total": len(rows),
            "data": [
                {
                    "id": r["answer_history_id"],
                    "question_id": r["question_id"],
                    "question_text": r["question_description"] or r["question_id"] or "",
                    "student_answer": r["student_ocr_answer"] or "",
                    "error_type": r["core_error_type"] or "未知",
                    "date": r["submitted_at"] or "",
                    "reviewed": False,
                    "wrong_count": 1,
                }
                for r in rows
            ],
        }


@app.get("/health")
def health_check():
    results = {}
    for service, url in SERVICE_URLS.items():
        try:
            response = requests.get(f"{url}/health", timeout=3)
            results[service] = response.json()
        except:
            results[service] = {"status": "unhealthy"}
    return {"api_gateway": "healthy", "services": results}

# ===== 前端静态文件托管（消除 CORS 问题） =====
_frontend_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "app_v2")
if _os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)