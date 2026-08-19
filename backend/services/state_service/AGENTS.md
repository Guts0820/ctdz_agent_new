# 学习状态服务说明

## 模块定位
监听 8085，维护学生在知识点上的正确次数、错误次数、掌握度和下一步动作，并生成复习计划。

## 架构
`main.py` 提供状态更新与复习生成 API，使用 `backend/shared/mastery_utils.py` 计算掌握度，数据写入集中 SQLite。

## 目录结构
- `main.py`：服务入口和状态迁移。
- `docs/README.md`：接口说明。

## 开发规范
状态更新必须可追踪且字段兼容现有网关。数据库路径统一为 `database/sqlite/example_db.db`，不得在模块目录创建数据库。

## 常用命令
运行 `python -m backend.services.state_service.main`；测试运行 `python -m pytest backend/tests -q`。

## 修改指南
变更掌握度阈值或状态机时，同时验证 Review 服务、网关 `state_client.py` 和数据库表。
