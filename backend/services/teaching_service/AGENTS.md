# 教学服务说明

## 模块定位
监听 8084，根据错因、知识范围和掌握度生成分层讲解、提示与练习，并执行推送频率检查。

## 架构
`main.py` 包含教学模式选择、LLM 调用、练习生成及频率接口；共享 LLM 和 ID 工具位于 `backend/shared/`。

## 目录结构
- `main.py`：FastAPI 入口与教学生成。
- `docs/README.md`：接口说明。

## 开发规范
提示和讲解必须适合目标年级。服务间请求设定超时；LLM 配置来自环境，日志不得包含密钥或完整学生数据。

## 常用命令
运行 `python -m backend.services.teaching_service.main`；测试运行 `python -m pytest backend/tests -q`。

## 修改指南
修改讲解字段、频控规则或教学模式时，同步检查网关响应和前端展示。
