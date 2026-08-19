# 后端模块说明

## 模块定位
后端包含 API 网关、九个独立业务服务、共享基础设施、测试和运行工具；前端与数据不属于本目录。

## 架构
`start_all.py` 初始化根目录 SQLite 后启动各服务。`api_gateway/` 是唯一外部入口；`services/` 中每个目录对应一个明确服务；`shared/` 只保存无业务归属的配置、ID、LLM、掌握度和观测工具。

## 目录结构
- `api_gateway/`：路由、编排与下游客户端。
- `services/`：判题、错因、知识、教学、教师端、状态、复习、图谱和 OCR。
- `shared/`：共享基础设施。
- `tests/`：后端回归与结构测试。
- `tools/`：数据库初始化、诊断与手工检查。
- `start_all.py`：本地服务编排。

## 开发规范
使用 Python、FastAPI、Pydantic、四空格和类型标注。服务不得把数据库或识别结果写入自身目录。跨服务 HTTP 必须设置超时；环境配置不得含硬编码密钥。路由只做协议适配，业务逻辑进入对应服务层。

## 常用命令
安装依赖：`python -m pip install -r backend/requirements.txt`。测试：`python -m pytest backend/tests -q`。编译检查：`python -m compileall backend`。启动：`python backend/start_all.py`。

## 修改指南
修改服务前阅读该服务 `AGENTS.md`。新增服务必须拥有明确目录、`AGENTS.md`、`docs/README.md`、入口和测试。调整数据库路径时统一指向根目录 `database/`。
