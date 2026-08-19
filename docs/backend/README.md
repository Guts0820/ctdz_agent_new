# 后端架构

`backend/start_all.py` 初始化 `database/sqlite/example_db.db`，随后启动 API 网关和八个独立服务。API 网关位于 `backend/api_gateway/`，其他服务各自位于 `backend/services/<service_name>/`，共享基础设施位于 `backend/shared/`。

正式提交链路为：OCR 结构化识别 -> 知识图谱匹配题目与标准答案 -> 判题 -> 错因 -> 知识讲解 -> 教学反馈 -> 状态与复习。前端独立运行，网关不托管静态文件。

执行 `python backend/start_all.py` 启动后端，执行 `python -m pytest backend/tests -q` 运行回归测试。
