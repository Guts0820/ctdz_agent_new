"""LLM 判题适配器及本模块专用配置。"""

import json
import os
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from backend.shared.http_client import create_direct_httpx_client


SERVICE_DIR = Path(__file__).resolve().parent
load_dotenv(SERVICE_DIR / ".env")


class LlmJudgeResult(BaseModel):
    """模型必须返回的最小、可验证判题结果。"""

    model_config = ConfigDict(extra="forbid")

    judge_result: Literal["correct", "wrong", "unknown"]
    step_feedback: str
    error_step_list: List[str]
    miss_step_list: List[str]
    core_error_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class QuestionRerankResult(BaseModel):
    """模型对候选题目的重排序结果。"""

    model_config = ConfigDict(extra="forbid")

    question_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    runner_up_confidence: float = Field(ge=0.0, le=1.0)
    reason: str


def _setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _client() -> OpenAI:
    api_key = _setting("ANALYSIS_LLM_API_KEY")
    if not api_key:
        raise RuntimeError("ANALYSIS_LLM_API_KEY is not configured")
    base_url = _setting(
        "ANALYSIS_LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=float(_setting("ANALYSIS_LLM_TIMEOUT_SECONDS", "60")),
        http_client=create_direct_httpx_client(),
    )


def _build_user_prompt(
    question: str,
    student_answer: str,
    standard_answer: str,
    standard_solve_steps: Optional[str],
) -> str:
    steps = standard_solve_steps or "（未提供标准步骤；只依据标准答案判断结果）"
    return f"""请判断学生是否正确作答。必须以【标准答案】为唯一正确性依据，允许学生采用与标准步骤不同但数学等价的解法。

【题目】
{question}

【学生作答】
{student_answer}

【标准答案】
{standard_answer}

【标准步骤（仅作参考）】
{steps}

判定要求：
1. 先独立核对学生最终结论与标准答案是否数学等价，再参考过程；不能因为步骤文字不同就判错。
2. 涂改、草稿、批注或无法确认的内容应判为 unknown，而不是猜测为正确。
3. 只输出 JSON，不要 Markdown、解释文字或额外字段。JSON 字段必须为：
{{
  "judge_result": "correct|wrong|unknown",
  "step_feedback": "简短反馈",
  "error_step_list": ["错误步骤"],
  "miss_step_list": ["缺失步骤"],
  "core_error_type": "错误类型，无错误时为空字符串",
  "confidence": 0.0
}}
"""


def _parse_json_content(content: Optional[str]) -> dict:
    if not content:
        raise ValueError("LLM returned an empty response")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("LLM response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object")
    return payload


def judge_with_llm(
    *,
    question: str,
    student_answer: str,
    standard_answer: str,
    standard_solve_steps: Optional[str] = None,
) -> dict:
    """调用本模块配置的 LLM，并返回通过 schema 校验的结果。"""

    model = _setting("ANALYSIS_LLM_MODEL", "qwen3.7-plus")
    completion = _client().chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "你是严格、保守的小学数学判题器。标准答案由系统提供，不能自行改写标准答案。",
            },
            {
                "role": "user",
                "content": _build_user_prompt(
                    question,
                    student_answer,
                    standard_answer,
                    standard_solve_steps,
                ),
            },
        ],
    )
    content = completion.choices[0].message.content
    payload = _parse_json_content(content)
    return LlmJudgeResult.model_validate(payload).model_dump()


def rerank_question_candidates(*, question: str, candidates: list[dict]) -> dict:
    """Ask the configured LLM to select one graph candidate using question text only."""
    candidate_payload = [
        {
            "question_id": str(candidate.get("id", "")),
            "question_text": str(candidate.get("text", "")),
            "retrieval_score": candidate.get("retrieval_score", 0.0),
        }
        for candidate in candidates
        if candidate.get("id") and candidate.get("text")
    ]
    if not candidate_payload:
        raise ValueError("No graph question candidates were provided")

    prompt = f"""请从候选题目中找出与 OCR 原题完全对应的一道题。只能选择候选列表中的 question_id。
不要使用学生答案、标准答案或候选题的相似度分数来猜测题意；只比较题干语义、人物、数字、条件、问题数量和图文语义。
如果没有可靠对应项，question_id 必须为 null。

【OCR 原题】
{question}

【候选题目】
{json.dumps(candidate_payload, ensure_ascii=False)}

只输出以下 JSON，不要 Markdown 或额外字段：
{{
  "question_id": "候选 question_id 或 null",
  "confidence": 0.0,
  "runner_up_confidence": 0.0,
  "reason": "简短匹配理由"
}}
"""
    completion = _client().chat.completions.create(
        model=_setting("ANALYSIS_LLM_MODEL", "qwen3.7-plus"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "你是严格的题目匹配器。无法确定时必须返回 null，不能根据学生答案猜题。",
            },
            {"role": "user", "content": prompt},
        ],
    )
    result = QuestionRerankResult.model_validate(
        _parse_json_content(completion.choices[0].message.content)
    ).model_dump()
    allowed_ids = {candidate["question_id"] for candidate in candidate_payload}
    if result["question_id"] is not None and result["question_id"] not in allowed_ids:
        raise ValueError("LLM selected a question outside the candidate set")
    return result
