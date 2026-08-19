# 共享基础设施说明

## 模块定位
保存多个后端服务共同使用、且不属于某个业务服务的基础设施代码；不得放入具体业务流程。

## 架构
`config.py` 统一加载 `backend/.env`，`http_client.py` 禁用环境代理继承，`llm_client.py` 封装 Qwen 文本模型，`neo4j_connection.py` 封装共享图连接，其余文件提供 ID、缓存、掌握度与观测工具。

## 目录结构
- `config.py`：环境与路径配置。
- `http_client.py`：统一禁用 `HTTP_PROXY`、`HTTPS_PROXY` 的继承，并创建直连 HTTPX 客户端。
- `llm_client.py`：Qwen 全系文本模型客户端。
- `neo4j_connection.py`：Neo4j 连接。
- `id_utils.py`、`cache_utils.py`、`mastery_utils.py`、`observability.py`：通用工具。

## 开发规范
共享代码必须无具体路由和业务编排。配置从环境读取；所有出站 HTTP 默认直连，不得继承系统代理；共享 LLM 只使用 `QWEN_API_KEY`、可选 `QWEN_BASE_URL` 和 `LLM_MODEL`；知识图谱向量配置使用 `QWEN_EMBEDDING_*` 和 `KG_VECTOR_*`，不得导入某个业务服务以避免反向依赖。

## 常用命令
相关回归测试运行 `python -m pytest backend/tests -q`，编译检查运行 `python -m compileall backend/shared`。

## 修改指南
修改共享配置或公共函数前搜索所有调用方；路径默认值必须从项目根目录解析到 `database/`。
