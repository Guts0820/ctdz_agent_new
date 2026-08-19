# Knowledge Graph Service

知识图谱服务监听 `8007`，通过 Neo4j 提供知识点、题目、错因、候选题召回和标准答案查询。应用入口是 `main.py`，路由位于 `routers/`，连接封装位于 `database.py`。

题库导入源统一位于 `database/knowledge_graph/image2_questions.json`。运行服务：`python -m backend.services.knowledge_graph_service.main`；候选召回：`GET /api/questions/candidates?text=...`；导入题库：`python backend/services/knowledge_graph_service/tools/import_image2_questions.py`。

知识点和错因资产导入：

```powershell
python backend/services/knowledge_graph_service/tools/import_knowledge_data.py
```

该脚本幂等导入 `database/seed/knowledge_points.csv`、`database/seed/knowledge_explanations.csv` 和 `database/reference/三级错因标签.xlsx`，创建 `KnowledgePoint`、`ErrorCause` 节点，并按错因的“知识点范围”建立 `(:ErrorCause)-[:APPLIES_TO]->(:KnowledgePoint)` 关系。Excel 不可用时回退到 SQLite 的 `error_bank` 表。

## 向量检索

知识图谱服务启动时创建 `Question.embedding` 的 Neo4j Vector Index。Embedding 使用 `backend/.env` 中的 Qwen 配置：

```env
QWEN_API_KEY=...
QWEN_EMBEDDING_MODEL=text-embedding-v3
QWEN_EMBEDDING_DIMENSIONS=1024
QWEN_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
KG_VECTOR_INDEX_NAME=question_embedding_index
```

题库导入和教师标准答案导入会生成 embedding；已有题目可执行 `python backend/services/knowledge_graph_service/tools/backfill_question_embeddings.py` 补向量。候选接口先执行向量召回，再合并词法结果。未配置 Embedding 密钥、索引不可用或请求失败时，接口回退到现有词法检索，不会阻断题目查询。

Embedding 请求默认直连，不继承系统 `HTTP_PROXY` 或 `HTTPS_PROXY`。
