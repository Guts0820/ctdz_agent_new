# Repository Guidelines

## 模块定位
仓库实现小学数学图片识别、标准答案判题、错因分析、教学反馈和复习。`frontend/`、`backend/` 与 `database/` 是互相独立的顶层边界。

## 架构
前端在 3000 独立运行并调用 8000 API 网关。网关依次编排 OCR（8089）、知识图谱（8007）、判题（8081）、错因（8082）、知识（8083）、教学（8084）、教师端（8090）、状态（8085）和复习（8087）。数据统一位于 `database/`。

## 实现状态
| 流程节点 | 实现状态 |
| --- | --- |
| 学生题目、答案或图片输入 | 已实现 |
| OCR 识别并分离题干与学生作答 | 已实现 |
| 知识图谱标准答案检索与判题 | 已实现 |
| 答对后更新掌握度 | 已实现 |
| 答错后三级错因分析与知识点关联 | 已实现 |
| 疑似抄袭判断 | 未实现 |
| 苏格拉底式引导追问与多轮对话 | 未实现 |
| 知识点讲解、常见错误与教学提示检索 | 已实现 |
| 讲解、提示与变式题生成 | 已实现 |
| BASIC / STANDARD / ADVANCED 教学分档 | 已实现 |
| Mastery + Priority 联动更新 | 部分实现 |

## 目录结构
- `frontend/`：静态网页与前端测试。
- `backend/api_gateway/`：对外 API 和跨服务编排。
- `backend/services/`：按服务划分的独立模块。
- `backend/shared/`：共享配置与基础设施。
- `database/`：SQLite、图谱导入、种子与参考数据。
- `docs/`：项目级文档。

## 开发规范
Python 使用四空格、类型标注和 `snake_case`；前端使用原生 JavaScript 与 `camelCase`。配置从环境读取，`.env`、密钥、图片和生产数据不得提交。跨模块调用使用 HTTP 客户端，禁止跨服务导入业务实现。

Git 提交信息使用 Conventional Commits 风格：保留 `feat:`、`fix:`、`test:`、`docs:` 等英文类型前缀，冒号后的标题正文使用中文。

## 常用命令
安装后端基础依赖：`python -m pip install -r backend/requirements.txt`。初始化数据库：`python backend/tools/init_sqlite_database.py`。启动后端：`python backend/start_all.py`。后端测试：`python -m pytest backend/tests -q`。前端测试：`node --test frontend/tests/ocr-upload-policy.test.js`。

## 修改指南
开始修改前阅读当前目录与目标服务的 `AGENTS.md`。端口、接口或数据路径变化必须同步更新调用方和模块文档。新行为先写失败测试；提交前运行受影响模块测试。
