# 数据目录说明

## 模块定位
集中保存项目运行数据、知识图谱导入数据、初始化种子和参考资料，不包含服务代码。

## 架构
SQLite 服务读取 `sqlite/`；知识图谱导入工具读取 `knowledge_graph/`；初始化脚本读取 `seed/` 和 `schema/`。Neo4j 实际存储由独立 Neo4j 服务管理。

## 目录结构
- `sqlite/`：SQLite 数据库。
- `knowledge_graph/`：Neo4j 导入 JSON。
- `seed/`：初始化 CSV。
- `schema/`：SQLite Schema。
- `reference/`：数据设计参考文件。

## 开发规范
不得提交生产数据、密钥或个人绝对路径。Schema 与种子数据变化必须可追踪；运行数据库修改前应备份。

## 常用命令
初始化 SQLite：`python backend/tools/init_sqlite_database.py`。导入图谱：`python backend/services/knowledge_graph_service/tools/import_image2_questions.py`。

## 修改指南
移动或重命名数据文件时同步检查 `backend/shared/config.py`、服务仓储和诊断工具。
