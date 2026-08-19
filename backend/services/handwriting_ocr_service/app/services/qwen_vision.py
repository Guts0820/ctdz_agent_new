import base64

import requests

from app.config import Settings
from app.models import EngineResult
from app.schemas import (
    JUDGING_INPUT_JSON_SCHEMA,
    STANDARD_ANSWER_INPUT_JSON_SCHEMA,
    validate_judging_input,
    validate_standard_answer_input,
)


class QwenVisionEngine:
    """OpenAI-compatible Qwen multimodal OCR and question-explanation engine."""

    def __init__(self, settings: Settings) -> None:
        if not settings.qwen_is_configured:
            raise RuntimeError("QWEN_API_KEY is required when OCR_ENGINE=qwen.")
        self._api_key = settings.qwen_api_key
        self._base_url = settings.qwen_base_url.rstrip("/")
        self._model = settings.qwen_model
        self._timeout_seconds = settings.qwen_timeout_seconds

    def recognize(self, image_bytes: bytes, content_type: str, mode: str = "student_work") -> EngineResult:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        schema_instruction = (
            "标准答案上传模式：识别图片中的每一道题，按题目分离；"
            "每道题的 question.text 为题干，question.explanation 为题目解释，"
            "student_answer.text 为教师提供的标准答案。"
            "只输出 questions 数组，不要合并多道题。\n"
            f"{STANDARD_ANSWER_INPUT_JSON_SCHEMA}"
            if mode == "standard_answer"
            else f"{JUDGING_INPUT_JSON_SCHEMA}"
        )
        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                        "你是小学数学作业图像理解服务。识别题目、学生作答、公式和图文信息，"
                        "并解释题目考查的已知条件与求解目标；不要判断学生答案正误，不要编造看不清的内容。"
                    ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded_image}"}},
                            {
                                "type": "text",
                                "text": (
                                    "只输出与以下 JSON Schema 匹配的 JSON，不要 Markdown 代码块。"
                                    "题目文本一般都是规整的印刷体，手写文本通常不规范，请仔细识别，"
                                    "在提取question.text时，只保留规整的题目文本，不要包含手写内容。"
                                    "执行题干与笔记分离：题干只保留原题的完整文字、公式和图形条件；"
                                    "草稿计算、旁注、批注、箭头、圈画、改写和作答都不得写入 question.text、"
                                    "question.explanation 或 visual_context，也不得用笔记中的数字补全或重建题干。"
                                    "若原题本身为手写，应根据题号、对齐、完整题目结构和与作答区的空间分隔判断，"
                                    "不能仅因其为手写就删除。若题干与笔记无法可靠分离，question.text 和 "
                                    "question.explanation 都设为空字符串，并将 review_required=true。"
                                    "提取 student_answer.text 时，只保留未被涂改、划掉、覆盖或删除的，"
                                    "完整且可辨认的最终作答，大部分情况为不规则的手写体；不得把被涂改的旧答案与最终答案拼接。"
                                    "例如答案栏中被划掉的 1740 和未涂改的 7950 同时存在时，"
                                    "student_answer.text 必须是 7950。若没有完整、未涂改且可辨认的作答，"
                                    "student_answer.text 设为空字符串，并将 review_required=true。\n"
                                    + schema_instruction
                                ),
                            },
                        ],
                    },
                ],
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        structured_result = (
            validate_standard_answer_input(str(content))
            if mode == "standard_answer"
            else validate_judging_input(str(content))
        )
        if mode == "standard_answer":
            recognized_questions = structured_result["questions"]
            text = "\n".join(
                f"题目：{item['question']['text']}\n标准答案：{item['student_answer']['text']}"
                for item in recognized_questions
            )
        else:
            question = structured_result["question"]
            student_answer = structured_result["student_answer"]
            text = f"题目：{question['text']}\n学生作答：{student_answer['text']}".strip()
        return EngineResult(
            text=text.strip(),
            confidence=float(structured_result["confidence"]),
            engine=self._model,
            content_format="plain_text",
            review_required=bool(structured_result["review_required"]),
            structured_result=structured_result,
        )
