# 知识服务说明

## 模块定位
监听 8083，根据知识点 ID 返回知识讲解、难度和标准解法；知识图谱查询由独立的 8007 服务负责。

## 架构
`main.py` 暴露知识检索接口并调用知识图谱 HTTP API，不拥有题目判题逻辑。

## 目录结构
- `main.py`：服务入口与知识检索。
- `docs/README.md`：接口说明。

## 开发规范
使用 Python、FastAPI、四空格和 `snake_case`。所有外部请求必须设置超时并将失败转换为明确 HTTP 错误。

## 常用命令
运行 `python -m backend.services.knowledge_service.main`；测试运行 `python -m pytest backend/tests -q`。

## 修改指南
响应字段变化时同步修改网关 `knowledge_client.py` 和教学链路；不要复制 Neo4j 数据访问代码。
