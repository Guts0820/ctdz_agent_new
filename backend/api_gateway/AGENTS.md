# API 网关说明

## 模块定位
监听 8000，是前端唯一业务 API 入口，负责协议适配、质量门禁和跨服务编排，不实现 OCR、判题或教学算法。

## 架构
`app.py` 只创建 FastAPI 应用并注册 `routers/`；路由调用 `services/` 中的业务编排或下游客户端；教师作业批次路由经 `teacher_client.py` 调用独立的 `teacher_service:8090`；共享配置和基础设施来自 `backend/shared/`。

## 目录结构
- `app.py`：应用入口。
- `routers/`：HTTP 路由。
- `services/`：提交编排、本地业务服务和下游客户端；不保留教师作业批次数据库逻辑。
- `models.py`：网关请求/响应模型。
- `docs/README.md`：接口边界。

## 开发规范
路由不得直接访问数据库或外部 HTTP。业务逻辑放入 `services/`；外部服务各自使用独立客户端。错误转换为明确 HTTP 状态，日志不得包含图片、密钥或完整答案。

## 常用命令
运行 `python -m backend.api_gateway.app`；测试运行 `python -m pytest backend/tests -q`。

## 修改指南
变更 API、端口或字段时同步检查前端、下游客户端和 OpenAPI。OCR 置信度低于 `0.95` 时必须中止判题。
