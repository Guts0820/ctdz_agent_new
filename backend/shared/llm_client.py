import os
from typing import Final

from openai import OpenAI
from dotenv import load_dotenv

from backend.shared.http_client import create_direct_httpx_client

# Keep the development configuration in ``backend/.env`` while allowing
# deployment environments to provide the variable directly.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


LLM_PROVIDERS: Final = {
    "qwen": {
        "api_key_env": "QWEN_API_KEY",
        "base_url_env": "QWEN_BASE_URL",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
}


def get_llm_provider() -> str:
    """Return the shared client's fixed provider."""
    return "qwen"


def get_llm_model(model: str | None = None) -> str:
    """Resolve an explicit Qwen model, then LLM_MODEL, then qwen-plus."""
    if model:
        return model
    configured_model = os.getenv("LLM_MODEL", "").strip()
    if configured_model:
        return configured_model
    return LLM_PROVIDERS[get_llm_provider()]["default_model"]


def get_llm_client() -> OpenAI:
    """Create a Qwen-compatible client from the current environment."""
    provider = get_llm_provider()
    config = LLM_PROVIDERS[provider]
    api_key = os.getenv(config["api_key_env"])
    if not api_key:
        raise RuntimeError(f"{config['api_key_env']} is not configured for Qwen")
    base_url = os.getenv(config["base_url_env"], "").strip() or config["base_url"]
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=create_direct_httpx_client(),
    )

def llm_enabled() -> bool:
    """LLM 是否可用。检查 Qwen API Key 是否已配置。"""
    config = LLM_PROVIDERS[get_llm_provider()]
    return bool(os.getenv(config["api_key_env"]))


def get_default_system_prompt() -> str:
    return "你是一个小学数学教学助手。"


def call_llm(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    completion = get_llm_client().chat.completions.create(
        model=get_llm_model(model),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content


def call_llm_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
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
