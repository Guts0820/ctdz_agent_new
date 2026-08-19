# CTDZ Agent

小学数学作业识别、判题、错因分析与复习系统。项目采用前后端分离架构：`frontend/` 是静态网页，`backend/` 包含 API 网关和独立服务，`database/` 集中保存 SQLite、知识图谱导入数据与种子数据。

## 服务架构

| 模块 | 端口 | 职责 |
| --- | --- | --- |
| API Gateway | 8000 | 对外路由与业务编排 |
| Analysis Service | 8081 | 根据标准答案判题 |
| Error Analysis Service | 8082 | 分析错因 |
| Knowledge Service | 8083 | 检索知识讲解 |
| Teaching Service | 8084 | 生成教学反馈 |
| Teacher Service | 8090 | 教师端作业批次管理 |
| State Service | 8085 | 更新掌握状态 |
| Review Service | 8087 | 复习计划、会话与订正 |
| Knowledge Graph Service | 8007 | Neo4j 题目与标准答案查询 |
| Handwriting OCR Service | 8089 | 图片识别与结构化输出 |

教师标准答案上传入口为 `POST /api/v1/teacher/standard_answers`，由教师服务调用 OCR 的标准答案模式，按题目拆分后写入 Neo4j。知识图谱题目匹配支持 Qwen Embedding 向量召回，并在配置缺失时回退词法检索。

## 本地启动

使用 Python 3.11，在仓库外创建虚拟环境并安装各模块依赖。配置 `backend/.env` 与 OCR 服务自己的 `.env` 后，从项目根目录执行：

```powershell
python backend/start_all.py
cd frontend
python -m http.server 3000
```

前端地址为 `http://127.0.0.1:3000`，API 网关为 `http://127.0.0.1:8000`。各模块的详细说明位于对应目录的 `docs/README.md`。
