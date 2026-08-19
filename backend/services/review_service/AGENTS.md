# 复习服务说明

## 模块定位
监听 8087，负责复习计划、会话、答题订正和优先级；`scheduler.py` 在 8086 处理到期复习任务。原 `Review2.0` 的独有掌握度与数据汇总代码已合并到本模块。

## 架构
`main.py` 注册 `review/api/` 路由；`review/` 按领域、仓储、Schema 和服务分层；`mastery/` 计算掌握度；`datahub/` 聚合学习路径和统计；`scheduler.py` 读取集中 SQLite。

## 目录结构
- `main.py`、`scheduler.py`：服务与调度入口。
- `review/`：复习领域实现。
- `mastery/`：掌握度计算。
- `datahub/`：统计与学习路径。
- `docs/README.md`：运行与边界说明。

## 开发规范
使用包内绝对导入。数据库只允许位于根目录 `database/`；路由只做 HTTP 适配，业务规则放入服务层。

## 常用命令
运行 `python -m backend.services.review_service.main`；测试运行 `python -m pytest backend/tests/test_review_service_import.py -q`。

## 修改指南
优先验证计划容量、会话状态、订正和优先级。接口变化需同步网关代理和前端 API。
