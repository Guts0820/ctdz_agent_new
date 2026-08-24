from typing import Literal

from pydantic import BaseModel, Field

from backend.shared.llm_client import call_llm_json


class QuestionSolution(BaseModel):
    answer: str = Field(min_length=1)
    solve_steps: list[str] = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"]


def solve_question_with_llm(*, question_text: str, grade: int, semester: str | None) -> dict:
    payload = call_llm_json(
        (
            "你是严谨的小学数学教师。独立解题，不猜测图片中未提供的信息。"
            "只返回符合要求的 JSON，不要输出 Markdown。"
        ),
        (
            f"适用年级：{grade} 年级\n"
            f"学期：{semester or '未指定'}\n"
            f"题目：{question_text}\n"
            "返回结构："
            '{"answer":"最终答案","solve_steps":["步骤1","步骤2"],'
            '"difficulty":"easy|medium|hard"}'
        ),
    )
    return QuestionSolution.model_validate(payload).model_dump()
