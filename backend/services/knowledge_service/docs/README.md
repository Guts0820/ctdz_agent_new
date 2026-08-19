# Knowledge Service

知识服务监听 `8083`，面向教学链路提供知识点讲解。它通过知识图谱服务读取知识数据，不直接连接 Neo4j。

入口：`python -m backend.services.knowledge_service.main`。
