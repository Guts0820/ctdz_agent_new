import json
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from backend.shared.id_utils import generate_id
from backend.shared.llm_client import call_llm


app = FastAPI(title="Teaching Service", version="1.1.0")
KG_SERVICE_URL = "http://127.0.0.1:8007"
DATABASE = "database/sqlite/example_db.db"


class ErrorTag(BaseModel):
    error_id: str
    level1: str
    level2: str
    level3: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class PracticeQuestion(BaseModel):
    question_id: str
    question_description: str = Field(min_length=1)
    difficulty: str
    answer: str = Field(min_length=1)
    solution: str = Field(min_length=1)


class TeachingGenerateRequest(BaseModel):
    error_tags: List[ErrorTag]
    knowledge_scope: str = Field(min_length=1)
    knowledge_id: Optional[str] = None
    master_level: float = Field(ge=0, le=1)
    original_question: str = Field(min_length=1)
    student_write: str
    difficulty: Optional[str] = "medium"
    grade: Optional[str] = "三年级"
    mistake_case_id: Optional[str] = None


class LLMTeachingContent(BaseModel):
    guided_explanation: str = Field(min_length=1)
    final_answer_explanation: str = Field(min_length=1)
    hints: List[str] = Field(min_length=2, max_length=3)
    reasoning_content: str = Field(min_length=1)

    @field_validator("hints")
    @classmethod
    def validate_hints(cls, hints: List[str]) -> List[str]:
        cleaned = [hint.strip() for hint in hints]
        if any(not hint for hint in cleaned):
            raise ValueError("提示不能为空")
        return cleaned

    @field_validator("guided_explanation")
    @classmethod
    def reject_direct_answer_in_guidance(cls, value: str) -> str:
        if re.search(r"(?:答案|结果|得数)\s*(?:是|为|=|：|:)", value):
            raise ValueError("引导讲解不能直接泄露最终答案")
        return value.strip()


class TeachingGenerateResponse(BaseModel):
    explanation: str
    guided_explanation: str
    final_answer_explanation: str
    hints: List[str]
    practice_list: List[PracticeQuestion]
    reasoning_content: str
    teaching_mode: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    practice_fallback_reason: Optional[str] = None


class FrequencyCheckRequest(BaseModel):
    student_id: str
    knowledge_id: str
    current_time: str


class FrequencyCheckResponse(BaseModel):
    push_permission: bool
    daily_push_count: int
    daily_limit: int
    weekly_push_count: int
    weekly_limit: int
    remaining_daily: int
    remaining_weekly: int


MODE_RULES = {
    "BASIC": {
        "description": "基础模式：语言具体、步骤完整，每一步只处理一个动作。",
        "hints": ["先找出题目要求的数量关系。", "按正确顺序完成第一步，再检查关键规则。", "完成后逐步验算，不要只看最后结果。"],
        "difficulty": "easy",
    },
    "STANDARD": {
        "description": "标准模式：突出方法、关键步骤和易错点，保留适量自主思考。",
        "hints": ["先说出这类题的计算或推理规则。", "检查易错步骤是否遗漏，再独立完成。"],
        "difficulty": "medium",
    },
    "ADVANCED": {
        "description": "进阶模式：简洁回顾核心规则，强调迁移、验算和多方法比较。",
        "hints": ["尝试用另一种方法验证你的过程。", "思考条件变化后，原来的规则是否仍然成立。"],
        "difficulty": "hard",
    },
}


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def select_teaching_mode(master_level: float) -> str:
    if master_level < 0.4:
        return "BASIC"
    if master_level <= 0.8:
        return "STANDARD"
    return "ADVANCED"


def convert_difficulty(value) -> str:
    if isinstance(value, str):
        normalized = value.lower().strip()
        return {"basic": "easy", "standard": "medium", "advanced": "hard"}.get(normalized, normalized)
    return {1: "easy", 2: "medium", 3: "hard"}.get(value, "medium")


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_teaching_with_llm(request: TeachingGenerateRequest, teaching_mode: str) -> LLMTeachingContent:
    mode_rule = MODE_RULES[teaching_mode]
    system_prompt = f"""你是一名小学数学教师。请根据题目、学生作答、错因和年级生成教学内容。
教学模式：{mode_rule['description']}
必须输出 JSON，字段为 guided_explanation、final_answer_explanation、hints、reasoning_content。
guided_explanation 只能讲错因、方法和思考路径，禁止出现“答案是/结果为/得数=”及最终答案。
final_answer_explanation 必须给出完整步骤和最终答案。
hints 必须为 2 至 3 条非空提示，不能直接给最终答案。
语言必须适合 {request.grade or '小学'}，不要使用超纲术语。"""
    user_prompt = json.dumps(
        {
            "original_question": request.original_question,
            "student_write": request.student_write,
            "knowledge_scope": request.knowledge_scope,
            "error_tags": [tag.model_dump() for tag in request.error_tags],
            "master_level": request.master_level,
            "teaching_mode": teaching_mode,
        },
        ensure_ascii=False,
    )
    parsed = json.loads(_strip_json_fence(call_llm(system_prompt, user_prompt)))
    return LLMTeachingContent.model_validate(parsed)


def build_template_fallback(request: TeachingGenerateRequest, teaching_mode: str) -> LLMTeachingContent:
    error_names = "、".join(tag.level3 for tag in request.error_tags) or "当前步骤存在错误"
    guided_by_mode = {
        "BASIC": f"这道题涉及“{request.knowledge_scope}”。先明确题目条件和目标，再按规则一步一步处理。你目前需要重点检查：{error_names}。每完成一步都核对所用规则。",
        "STANDARD": f"这道题的核心知识是“{request.knowledge_scope}”。先写出方法，再定位关键步骤；结合错因“{error_names}”重新检查过程并验算。",
        "ADVANCED": f"围绕“{request.knowledge_scope}”，请先概括核心规则，再用第二种方法验证。重点反思“{error_names}”在条件变化时是否还会出现。",
    }
    return LLMTeachingContent(
        guided_explanation=guided_by_mode[teaching_mode],
        final_answer_explanation="当前题库没有可核验的标准答案，暂不展示完整答案；请由上游判题结果或教师确认后补充。",
        hints=MODE_RULES[teaching_mode]["hints"],
        reasoning_content=f"LLM 不可用或输出非法，按掌握度 {request.master_level:.2f} 使用 {teaching_mode} 模板降级。",
    )


def fetch_practice_questions(knowledge_id: str, difficulty: str, count: int = 2) -> tuple[List[Dict], Optional[str]]:
    if not knowledge_id:
        return [], "未提供 knowledge_id，无法从题库检索变式题"
    try:
        response = requests.post(
            f"{KG_SERVICE_URL}/api/recommend",
            json={"knowledge_ids": [knowledge_id], "count": count, "difficulty": difficulty},
            timeout=10,
        )
        response.raise_for_status()
        questions = response.json().get("recommended_questions", [])
        if not questions:
            return [], f"知识点 {knowledge_id} 暂无 {difficulty} 难度的已核验题目"
        return questions, None
    except (requests.exceptions.RequestException, ValueError, TypeError) as error:
        return [], f"题库检索不可用: {type(error).__name__}"


def build_practice_list(questions: List[Dict], default_difficulty: str) -> List[PracticeQuestion]:
    practice = []
    for question in questions:
        description = str(question.get("text") or question.get("question") or "").strip()
        answer = str(question.get("answer") or "").strip()
        raw_solution = question.get("explanation") or question.get("answer_steps") or ""
        solution = "\n".join(raw_solution) if isinstance(raw_solution, list) else str(raw_solution).strip()
        if not description or not answer or not solution:
            continue
        practice.append(
            PracticeQuestion(
                question_id=str(question.get("id") or generate_id("Q")),
                question_description=description,
                difficulty=convert_difficulty(question.get("difficulty", default_difficulty)),
                answer=answer,
                solution=solution,
            )
        )
    return practice


def save_teaching_content(request: TeachingGenerateRequest, response: TeachingGenerateResponse) -> None:
    with get_db() as connection:
        connection.execute(
            """INSERT INTO teaching_content (
                teaching_content_id, mistake_case_id, explanation, hints,
                practice_list, reasoning_content, master_level, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                generate_id("TC"), request.mistake_case_id or "", response.explanation,
                json.dumps(response.hints, ensure_ascii=False),
                json.dumps([item.model_dump() for item in response.practice_list], ensure_ascii=False),
                response.reasoning_content, request.master_level, datetime.now().isoformat(),
            ),
        )
        connection.commit()


@app.post("/internal/api/v1/teaching/generate", response_model=TeachingGenerateResponse)
def generate_teaching(request: TeachingGenerateRequest):
    teaching_mode = select_teaching_mode(request.master_level)
    fallback_used = False
    fallback_reason = None
    try:
        content = generate_teaching_with_llm(request, teaching_mode)
    except Exception as error:
        fallback_used = True
        fallback_reason = f"教学模型不可用或输出非法: {type(error).__name__}"
        content = build_template_fallback(request, teaching_mode)

    target_difficulty = MODE_RULES[teaching_mode]["difficulty"]
    raw_questions, practice_fallback_reason = fetch_practice_questions(
        request.knowledge_id or "", target_difficulty, count=2
    )
    practice_list = build_practice_list(raw_questions, target_difficulty)
    if raw_questions and not practice_list:
        practice_fallback_reason = "题库候选缺少题干、答案或解析，已过滤全部候选"

    response = TeachingGenerateResponse(
        explanation=f"{content.guided_explanation}\n\n{content.final_answer_explanation}",
        guided_explanation=content.guided_explanation,
        final_answer_explanation=content.final_answer_explanation,
        hints=content.hints,
        practice_list=practice_list,
        reasoning_content=content.reasoning_content,
        teaching_mode=teaching_mode,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        practice_fallback_reason=practice_fallback_reason,
    )
    save_teaching_content(request, response)
    return response


@app.post("/internal/api/v1/teaching/frequency-check", response_model=FrequencyCheckResponse)
def check_frequency(request: FrequencyCheckRequest):
    daily_limit = 5
    weekly_limit = 3
    with get_db() as connection:
        row = connection.execute(
            """SELECT daily_push_count, weekly_push_count, last_reset_date
            FROM frequency_limit WHERE student_id = ? AND knowledge_id = ?""",
            (request.student_id, request.knowledge_id),
        ).fetchone()
        if row:
            daily_push_count = row["daily_push_count"]
            weekly_push_count = row["weekly_push_count"]
            if row["last_reset_date"] != str(datetime.now().date()):
                daily_push_count = 0
                connection.execute(
                    """UPDATE frequency_limit SET daily_push_count = 0, last_reset_date = ?
                    WHERE student_id = ? AND knowledge_id = ?""",
                    (str(datetime.now().date()), request.student_id, request.knowledge_id),
                )
                connection.commit()
        else:
            daily_push_count = 0
            weekly_push_count = 0
            connection.execute(
                """INSERT INTO frequency_limit (
                    frequency_limit_id, student_id, knowledge_id,
                    daily_push_count, weekly_push_count, last_reset_date
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (generate_id("FL"), request.student_id, request.knowledge_id, 0, 0, str(datetime.now().date())),
            )
            connection.commit()
    return FrequencyCheckResponse(
        push_permission=daily_push_count < daily_limit and weekly_push_count < weekly_limit,
        daily_push_count=daily_push_count,
        daily_limit=daily_limit,
        weekly_push_count=weekly_push_count,
        weekly_limit=weekly_limit,
        remaining_daily=max(0, daily_limit - daily_push_count),
        remaining_weekly=max(0, weekly_limit - weekly_push_count),
    )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Teaching Service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8084)
