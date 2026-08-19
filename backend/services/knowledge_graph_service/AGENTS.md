# 知识图谱服务说明

## 模块定位

本模块是小学数学知识图谱的独立 FastAPI 查询服务，提供知识点、题目和错因数据给主网关及其他调用方使用。主编排以 `:8007` 启动它。

## 架构

`main.py` 创建应用、配置 CORS、在启动/关闭阶段连接 Neo4j 并创建向量索引，注册题目、知识点、错因和内部标准答案写入路由。`embedding.py` 使用 backend `.env` 中的 Qwen Embedding 配置生成题干向量；`vector_index.py` 创建 `Question.embedding` 的 Neo4j Vector Index；`database.py` 封装 Neo4j 连接和查询，`models.py` 定义 Pydantic 模型。`/api/questions/candidates?text=...` 优先执行向量召回，再合并规范化精确、字符 n-gram 和序列相似度结果；向量服务或索引不可用时自动回退词法召回。内部 `/internal/api/questions/standard-answer` 和题库导入会生成并保存 embedding。

## 目录结构

- `main.py`：应用入口、生命周期和健康/统计接口。
- `database.py`：Neo4j 连接封装。
- `models.py`：数据模型。
- `routers/`：知识点、题目、错因查询路由。
- `../../../database/knowledge_graph/image2_questions.json`：已核对的题干、标准答案与解题步骤。
- `tools/import_image2_questions.py`：按题目 ID 幂等导入 image2 题库及题目别名。
- `routers/internal_questions.py`：接收教师服务提交的已校验标准答案字段。
- `embedding.py`：Qwen Embedding 客户端和题目文本构造。
- `vector_index.py`：Neo4j 向量索引创建。
- `tools/backfill_question_embeddings.py`：为 Neo4j 中已有题目补生成 embedding。
- `requirements.txt`：FastAPI、Neo4j 等依赖。
- `docs/README.md`：当前接口与运行说明；示例配置不得作为真实凭据来源。

## 开发规范

使用 Python、FastAPI、Pydantic 和四空格缩进。连接配置由 `.env` 提供，绝不提交密码或生产连接串。Embedding 模型维度必须与 Neo4j Vector Index 一致，云端请求默认直连；API 不可用时不得阻断词法检索。保持路由响应中文 UTF-8 和分页参数的兼容性；数据库异常应转换成合适的 HTTP 错误。

## 常用命令

从仓库根目录执行 `python -m pip install -r backend\services\knowledge_graph_service\requirements.txt`，再运行 `python -m backend.services.knowledge_graph_service.main`。服务端口读取 `API_PORT`，主编排中使用 `8007`；可用 `GET /health` 验证连接。

测试运行 `python -m pytest backend\services\knowledge_graph_service\tests -q`。导入题库时执行 `python backend\services\knowledge_graph_service\tools\import_image2_questions.py`；已有题目补向量执行 `python backend\services\knowledge_graph_service\tools\backfill_question_embeddings.py`。脚本使用 `Question.id` 的 `MERGE`，可安全重复执行。

## 修改指南

修改 Cypher、标签、关系、候选评分或模型字段前确认对判题服务、主网关、复习服务和前端查询的影响。新增路由需在 `main.py` 注册，并验证空数据、Neo4j 不可用、候选歧义和中文响应场景。不要把 README 的示例密码复制到环境文件或代码。
