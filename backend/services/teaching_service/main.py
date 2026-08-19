import json
import re
import sys
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import requests
sys.path.insert(0, 'backend/services')
from backend.shared.id_utils import generate_id
from backend.shared.llm_client import call_llm

app = FastAPI(title="Teaching Service", version="1.0.0")

KG_SERVICE_URL = "http://127.0.0.1:8007"

DATABASE = "database/sqlite/example_db.db"

class ErrorTag(BaseModel):
    error_id: str
    level1: str
    level2: str
    level3: str

def convert_difficulty(value) -> str:
    if isinstance(value, str):
        return value
    difficulty_map = {1: "easy", 2: "medium", 3: "hard"}
    return difficulty_map.get(value, "medium")

class PracticeQuestion(BaseModel):
    question_id: str
    question_description: str
    difficulty: str
    answer: str
    solution: str

class TeachingGenerateRequest(BaseModel):
    error_tags: List[ErrorTag]
    knowledge_scope: str
    knowledge_id: Optional[str] = None
    master_level: float
    original_question: str
    student_write: str
    difficulty: Optional[str] = "medium"
    grade: Optional[str] = "三年级"

class TeachingGenerateResponse(BaseModel):
    explanation: str  # 兼容旧调用方，内容 = guided_explanation + final_answer_explanation
    guided_explanation: str  # 引导性讲解（不包含最终答案数字，学生随时可见）
    final_answer_explanation: str  # 完整答案讲解（需要老师放行后才可见）
    hints: List[str]
    practice_list: List[PracticeQuestion]
    reasoning_content: str
    teaching_mode: str

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

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

TEACHING_TEMPLATES = {
    "K035": {
        "basic_explain": "我们来学习两位数加两位数的进位加法。当两个数相加时，个位上的数字加起来如果等于或超过10，就要向十位进1。比如25+38，个位5+8=13，我们在个位写3，然后向十位进1，十位上2+3再加上进位的1等于6，所以结果是63。",
        "standard_explain": "两位数加两位数进位加法的计算方法：1. 相同数位对齐；2. 从个位加起；3. 个位相加满十，向十位进1；4. 十位相加时要记得加上进位的1。",
        "advanced_explain": "你已经掌握了进位加法的基本方法，继续加油！记住进位标记很重要哦。",
        "basic_hints": ["先算个位，5+8等于多少？", "个位满十了吗？满十要怎么办？", "十位上的2+3还要加什么？"],
        "standard_hints": ["检查一下个位相加是否满十", "十位相加时有没有忘记加进位"],
        "advanced_hints": ["你能说说进位加法的关键步骤吗？", "如果个位相加等于9，需要进位吗？"],
        "basic_practice": [
            {"question": "18+25=？", "answer": "43", "solution": "个位8+5=13，写3进1；十位1+2+1=4"},
            {"question": "36+17=？", "answer": "53", "solution": "个位6+7=13，写3进1；十位3+1+1=5"}
        ],
        "standard_practice": [
            {"question": "45+28=？", "answer": "73", "solution": "个位5+8=13，写3进1；十位4+2+1=7"},
            {"question": "56+37=？", "answer": "93", "solution": "个位6+7=13，写3进1；十位5+3+1=9"}
        ]
    },
    "K037": {
        "basic_explain": "我们来学习两位数减两位数的退位减法。当个位上的数字不够减时，要从十位借1当10。比如52-28，个位2-8不够减，从十位借1变成12，12-8=4；十位上5被借走1剩4，4-2=2，所以结果是24。",
        "standard_explain": "两位数减两位数退位减法的计算方法：1. 相同数位对齐；2. 从个位减起；3. 个位不够减，从十位退1；4. 十位相减时要减去退走的1。",
        "advanced_explain": "你已经掌握了退位减法的基本方法，注意退位标记哦！",
        "basic_hints": ["个位2-8够减吗？不够减怎么办？", "从十位借1后，个位变成多少？", "十位上的5被借走1后还剩多少？"],
        "standard_hints": ["检查一下个位是否需要退位", "十位相减时有没有忘记减退位"],
        "advanced_hints": ["你能说说退位减法的关键步骤吗？", "如果个位刚好够减，还需要退位吗？"],
        "basic_practice": [
            {"question": "42-18=？", "answer": "24", "solution": "个位2-8不够减，借1得12-8=4；十位4-1-1=2"},
            {"question": "53-27=？", "answer": "26", "solution": "个位3-7不够减，借1得13-7=6；十位5-1-2=2"}
        ],
        "standard_practice": [
            {"question": "64-38=？", "answer": "26", "solution": "个位4-8不够减，借1得14-8=6；十位6-1-3=2"},
            {"question": "72-45=？", "answer": "27", "solution": "个位2-5不够减，借1得12-5=7；十位7-1-4=2"}
        ]
    },
    "default": {
        "basic_explain": "我们来复习这个知识点。仔细看题目，按照正确的方法一步步计算。",
        "standard_explain": "这个知识点的关键是理解计算方法，按照步骤来做。",
        "advanced_explain": "你已经基本掌握了这个知识点，继续巩固！",
        "basic_hints": ["第一步应该做什么？", "这里需要注意什么？", "再检查一遍计算过程"],
        "standard_hints": ["检查一下计算步骤", "有没有遗漏什么？"],
        "advanced_hints": ["你能说说这个知识点的关键吗？", "如果换一种方法会怎么做？"],
        "basic_practice": [
            {"question": "练习题1", "answer": "答案1", "solution": "解析1"},
            {"question": "练习题2", "answer": "答案2", "solution": "解析2"}
        ],
        "standard_practice": [
            {"question": "变式题1", "answer": "答案1", "solution": "解析1"},
            {"question": "变式题2", "answer": "答案2", "solution": "解析2"}
        ]
    }
}

def get_teaching_template(knowledge_scope: str) -> dict:
    if "加法" in knowledge_scope:
        return TEACHING_TEMPLATES["K035"]
    elif "减法" in knowledge_scope:
        return TEACHING_TEMPLATES["K037"]
    else:
        return TEACHING_TEMPLATES["default"]

def fetch_practice_questions(knowledge_id: str, count: int = 2) -> List[Dict]:
    if not knowledge_id:
        return []
    try:
        response = requests.post(
            f"{KG_SERVICE_URL}/api/recommend",
            json={"knowledge_ids": [knowledge_id], "count": count},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("recommended_questions", [])
    except requests.exceptions.RequestException as e:
        print(f"获取候选练习题失败: {e}")
        return []

def generate_teaching_with_llm(request: TeachingGenerateRequest, teaching_mode: str) -> Tuple[str, str, List[str], str]:
    error_tags_str = json.dumps([tag.dict() for tag in request.error_tags], ensure_ascii=False, indent=2)

    if teaching_mode == "BASIC":
        mode_desc = "基础模式：学生对该知识点掌握较弱，讲解要通俗易懂，用简单的语言和形象的例子"
    elif teaching_mode == "STANDARD":
        mode_desc = "标准模式：学生对该知识点有一定基础，讲解注重方法步骤和关键点"
    else:
        mode_desc = "进阶模式：学生已基本掌握，讲解以拓展和巩固为主"

    system_prompt = f"""你是一位经验丰富的小学数学老师，擅长根据学生的错题情况进行个性化讲解。

## 教学模式
{mode_desc}

## 知识点
{request.knowledge_scope}

## 错因分析
{error_tags_str}

## 讲解要求（重要：必须拆分成两部分）
1. guided_explanation：引导性讲解，帮助学生理解错误原因和正确方法，但**不要出现最终答案数字**。这是学生随时可见的内容。
2. final_answer_explanation：完整答案讲解，包含正确的计算过程和最终答案数字。这需要老师放行后学生才能看到。
3. hints：2-3条引导性提示，不要直接给答案，要引导学生思考
4. reasoning_content：教学推理过程，说明你是如何根据错因和掌握度来生成讲解内容的

## 输出格式
请严格按照以下JSON格式输出，不要输出任何多余内容：
{{
    "guided_explanation": "引导性讲解（不含最终答案）",
    "final_answer_explanation": "完整答案讲解（含最终答案）",
    "hints": ["提示1", "提示2", "提示3"],
    "reasoning_content": "教学推理过程"
}}

## 示例
题目：小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？
学生作答：25+38=53
错因：计算-进位加法中十位漏加进位1
掌握度：0.3（基础模式）

输出：
{{
    "guided_explanation": "这道题考查的是两位数加两位数的进位加法。计算时要注意：相同数位对齐，从个位加起，个位相加满十要向十位进1。比如这道题，个位相加等于13，写3进1；十位上2+3还要加上进位的1。你在十位计算时忘记加上进位的1了哦。",
    "final_answer_explanation": "正确答案是63。计算过程：个位5+8=13，写3进1；十位2+3+1=6，所以答案是63。",
    "hints": ["个位5+8等于多少？", "个位满十了吗？满十要向哪一位进1？", "十位上的2+3还要再加什么？"],
    "reasoning_content": "学生在十位计算时漏加了进位1，说明对进位加法的算理理解不够牢固，采用基础模式，用具体的例子一步步讲解进位的过程。"
}}"""

    user_prompt = f"""请为以下学生生成个性化教学内容：

题目：{request.original_question}
学生作答：{request.student_write}
知识点：{request.knowledge_scope}
教学模式：{teaching_mode}
掌握度：{request.master_level}
年级：{request.grade}

请按照要求的JSON格式输出教学内容。"""

    llm_response = call_llm(system_prompt, user_prompt)

    llm_response = llm_response.strip()
    if llm_response.startswith("```json"):
        llm_response = llm_response[7:]
    if llm_response.startswith("```"):
        llm_response = llm_response[3:]
    if llm_response.endswith("```"):
        llm_response = llm_response[:-3]

    try:
        parsed = json.loads(llm_response)
    except json.JSONDecodeError:
        raise ValueError("LLM返回格式错误，无法解析JSON")

    guided_explanation = parsed.get("guided_explanation", "")
    final_answer_explanation = parsed.get("final_answer_explanation", "")
    hints = parsed.get("hints", [])
    reasoning_content = parsed.get("reasoning_content", "")

    if not guided_explanation or not final_answer_explanation or not hints:
        raise ValueError("LLM返回内容不完整")

    return guided_explanation, final_answer_explanation, hints, reasoning_content

@app.post("/internal/api/v1/teaching/generate", response_model=TeachingGenerateResponse)
def generate_teaching(request: TeachingGenerateRequest):
    if request.master_level < 0.4:
        teaching_mode = "BASIC"
    elif 0.4 <= request.master_level <= 0.8:
        teaching_mode = "STANDARD"
    else:
        teaching_mode = "ADVANCED"

    template = get_teaching_template(request.knowledge_scope)

    try:
        guided_explanation, final_answer_explanation, hints, reasoning_content = generate_teaching_with_llm(request, teaching_mode)
    except Exception as e:
        print(f"LLM生成教学内容失败，降级为模板匹配。错误详情: {e}")
        if teaching_mode == "BASIC":
            template_explain = template["basic_explain"]
            hints = template["basic_hints"]
        elif teaching_mode == "STANDARD":
            template_explain = template["standard_explain"]
            hints = template["standard_hints"]
        else:
            template_explain = template["advanced_explain"]
            hints = template["advanced_hints"]

        # 模板内容作为完整讲解，拆分成两部分
        # 引导部分：去掉最终答案数字（简单处理：截取前半部分）
        guided_explanation = template_explain
        final_answer_explanation = f"（完整答案讲解）{template_explain}"
        reasoning_content = f"基于知识点'{request.knowledge_scope}'和掌握度{request.master_level:.2f}，生成{teaching_mode}模式的教学内容。错因：{[tag.level3 for tag in request.error_tags]}"

    # 拼接两部分作为 explanation（兼容旧调用方）
    explanation = f"{guided_explanation}\n\n{final_answer_explanation}"

    practice_list = []
    if teaching_mode != "ADVANCED" and request.knowledge_id:
        practice_questions = fetch_practice_questions(request.knowledge_id, count=2)
        for q in practice_questions:
            practice_list.append(PracticeQuestion(
                question_id=q.get("id", generate_id("Q")),
                question_description=q.get("text", q.get("question", "")),
                difficulty=convert_difficulty(q.get("difficulty", request.difficulty)),
                answer=q.get("answer", ""),
                solution=""
            ))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO teaching_content (
                teaching_content_id, mistake_case_id, explanation, hints,
                practice_list, reasoning_content, master_level, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            generate_id("TC"),
            "",
            explanation,
            json.dumps(hints),
            json.dumps([p.dict() for p in practice_list]),
            reasoning_content,
            request.master_level,
            datetime.now().isoformat()
        ))
        conn.commit()

    return TeachingGenerateResponse(
        explanation=explanation,
        guided_explanation=guided_explanation,
        final_answer_explanation=final_answer_explanation,
        hints=hints,
        practice_list=practice_list,
        reasoning_content=reasoning_content,
        teaching_mode=teaching_mode
    )

@app.post("/internal/api/v1/teaching/frequency-check", response_model=FrequencyCheckResponse)
def check_frequency(request: FrequencyCheckRequest):
    daily_limit = 5
    weekly_limit = 3
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT daily_push_count, weekly_push_count, last_reset_date
            FROM frequency_limit
            WHERE student_id = ? AND knowledge_id = ?
        ''', (request.student_id, request.knowledge_id))
        row = cursor.fetchone()
        
        if row:
            daily_push_count = row["daily_push_count"]
            weekly_push_count = row["weekly_push_count"]
            last_reset_date = row["last_reset_date"]
            
            today = datetime.now().date()
            if last_reset_date != str(today):
                daily_push_count = 0
                cursor.execute('''
                    UPDATE frequency_limit
                    SET daily_push_count = 0, last_reset_date = ?
                    WHERE student_id = ? AND knowledge_id = ?
                ''', (str(today), request.student_id, request.knowledge_id))
                conn.commit()
        else:
            daily_push_count = 0
            weekly_push_count = 0
            cursor.execute('''
                INSERT INTO frequency_limit (
                    frequency_limit_id, student_id, knowledge_id,
                    daily_push_count, weekly_push_count, last_reset_date
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (generate_id("FL"), request.student_id, request.knowledge_id, 0, 0, str(datetime.now().date())))
            conn.commit()
    
    push_permission = daily_push_count < daily_limit and weekly_push_count < weekly_limit
    
    return FrequencyCheckResponse(
        push_permission=push_permission,
        daily_push_count=daily_push_count,
        daily_limit=daily_limit,
        weekly_push_count=weekly_push_count,
        weekly_limit=weekly_limit,
        remaining_daily=daily_limit - daily_push_count,
        remaining_weekly=weekly_limit - weekly_push_count
    )

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Teaching Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)
