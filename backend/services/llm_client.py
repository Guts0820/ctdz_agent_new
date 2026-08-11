import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_client = OpenAI(
    api_key=os.getenv("QIANFAN_API_KEY"),
    base_url="https://qianfan.baidubce.com/v2"
)

def llm_enabled() -> bool:
    """LLM 是否可用。检查 API Key 是否已配置。"""
    return bool(os.getenv("QIANFAN_API_KEY"))


def get_default_system_prompt() -> str:
    return "你是一个小学数学教学助手。"


def call_llm(system_prompt: str, user_prompt: str, model: str = "ernie-4.5-turbo-32k") -> str:
    completion = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content


def call_llm_json(system_prompt: str, user_prompt: str, model: str = "ernie-4.5-turbo-32k") -> dict:
    """调用 LLM 并解析 JSON 返回。失败抛异常。"""
    import json as _json
    raw = call_llm(system_prompt, user_prompt, model)
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return _json.loads(raw)