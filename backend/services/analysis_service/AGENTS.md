# 判题服务说明

## 模块定位
监听 8081，接收 OCR/网关整理后的题干和学生作答，负责从知识图谱候选中确认题目、取得标准答案、最终判定并写入答题历史。不负责 OCR；图谱数据仍由 `knowledge_graph_service` 所有。

## 架构
`main.py` 负责 FastAPI 契约、匹配门禁和持久化；`question_retrieval.py` 通过知识图谱服务召回候选，并要求 LLM 重排序置信度和候选间隔达标；`llm_judge.py` 使用本模块独立 `.env` 调用 Qwen。确认题目后，模型必须参考图谱标准答案返回受限 JSON；模型不可用时仅允许规范化精确匹配，模糊候选不得猜测。

## 目录结构
- `main.py`：服务入口、判题编排和答题历史写入。
- `llm_judge.py`：模块专用 LLM 配置、提示词和 JSON Schema 校验。
- `question_retrieval.py`：候选召回客户端、LLM 重排序和匹配置信度门禁。
- `.env.example`：本模块配置模板，不含密钥。
- `docs/README.md`：接口、配置和运行说明。

## 开发规范
使用 Python、四空格、类型标注和 `snake_case`。学生答案不得参与题目召回；标准答案只能来自已确认的图谱候选。LLM 输出必须先通过 `LlmJudgeResult` 或匹配结果 schema 校验，云端请求默认直连且密钥不得记录或提交。数据库路径从共享配置读取。

## 常用命令
从项目根目录运行 `python -m backend.services.analysis_service.main`；测试运行 `python -m pytest backend/tests/test_standard_answer_judging.py -q`；编译检查运行 `python -m compileall backend/services/analysis_service`。

## 修改指南
修改召回、匹配门槛、判题字段、提示词或 schema 时，补充正确、错误、等价步骤、候选歧义、非法响应和降级测试，并同步检查网关提交契约与本目录文档。
