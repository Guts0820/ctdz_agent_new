# Shared Infrastructure

本目录包含后端共享配置、Qwen 全系文本模型客户端、Neo4j 连接、ID、缓存、掌握度和观测工具。它不提供独立 HTTP 服务，也不拥有业务数据。

共享 LLM 从 `backend/.env` 读取 `QWEN_API_KEY`、可选 `QWEN_BASE_URL` 和 `LLM_MODEL`。`LLM_MODEL` 可填写任意可用 Qwen 型号，例如 `qwen-plus`、`qwen-max` 或已开通的其他文本模型；未配置时默认 `qwen-plus`。

所有后端出站 HTTP 默认忽略 `HTTP_PROXY` 和 `HTTPS_PROXY`，直接访问本机服务和云端模型接口。Qwen 的 OpenAI 兼容客户端也显式使用 `trust_env=False`。
