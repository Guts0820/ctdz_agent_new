# 教师端服务说明

## 模块定位

本模块是教师端后端业务边界，负责作业批次管理和标准答案图片导入。API 网关只保留对外协议和转发；Neo4j 的节点写入仍由知识图谱服务负责。

## 架构

`main.py` 创建 FastAPI 应用并注册教师路由；`routers/` 负责内部 HTTP 契约；`homework_batch_service.py` 编排批次状态和 SQLite 写入；`standard_answer_service.py` 调用 OCR 的 `standard_answer` 模式，校验置信度并将选定字段交给知识图谱服务；`database.py` 提供本模块数据库连接。网关通过教师服务地址调用教师内部接口。

## 目录结构

- `main.py`：服务入口和健康检查，默认端口 `8090`。
- `models.py`：批次请求和响应模型。
- `routers/`：教师端内部路由。
- `homework_batch_service.py`：批次创建、整批放行、部分放行逻辑。
- `standard_answer_service.py`：标准答案 OCR 编排、字段映射和图谱写入请求。
- `question_import_service.py`：教师题目录入预览、幂等暂存及已有题目复用。
- `question_solver.py`、`answer_comparison.py`：新题独立解题和答案等价比较。
- `routers/standard_answers.py`：标准答案图片上传接口。
- `routers/question_imports.py`：教师题目录入预览接口。
- `database.py`：共享 SQLite 文件连接。
- `docs/README.md`：接口说明。

## 开发规范

使用 Python、FastAPI、Pydantic、四空格和类型标注。路由只做协议适配，业务逻辑放入服务层；数据库路径从共享配置读取。跨服务调用由网关客户端完成，日志不得写入密钥、图片或完整学生答案。

## 常用命令

从项目根目录运行 `python -m backend.services.teacher_service.main`；测试运行 `python -m pytest backend/tests/test_teacher_service_boundary.py -q`；编译检查运行 `python -m compileall backend/services/teacher_service`。

## 修改指南

新增教师功能应先放入本模块，再由网关增加代理路由。标准答案导入只允许写入 OCR 已校验且置信度达到 `0.95` 的题目；预览确认前只能写教师导入暂存表，不得写正式题库。题干、解释和答案字段的映射变化必须同步检查知识图谱接口。修改批次状态或数据库字段时同步检查提交服务的放行校验、前端 `teacher.js` 和 SQLite 初始化脚本，并运行后端回归测试。
