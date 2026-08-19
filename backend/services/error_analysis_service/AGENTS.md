# 错因分析服务说明

## 模块定位
监听 8082，根据判题结果和作答过程生成结构化错因标签，供教学与状态服务消费。

## 架构
`main.py` 提供完整与轻量错因分析接口，使用共享 LLM 客户端、ID 工具和集中 SQLite 数据。

## 目录结构
- `main.py`：FastAPI 入口与错因分析逻辑。
- `docs/README.md`：接口说明。

## 开发规范
使用 Python、四空格和明确的 Pydantic 模型。LLM 不可用时应返回可解释错误；不得记录密钥或完整学生作答。

## 常用命令
运行 `python -m backend.services.error_analysis_service.main`；相关回归测试使用 `python -m pytest backend/tests -q`。

## 修改指南
调整错因标签、置信度或持久化字段时，同步检查教学服务输入和数据库 Schema。
