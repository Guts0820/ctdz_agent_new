# Database

本目录集中管理所有数据资产。`sqlite/` 是运行数据库，`knowledge_graph/` 是 Neo4j 导入源，`seed/` 用于初始化；`schema/schema.sql` 是最初的设计稿（MySQL 语法），不被任何脚本执行，运行 Schema 以 `backend/tools/init_sqlite_database.py` 为准。服务目录不得再生成 `.db`、`.csv` 或题库 JSON。
