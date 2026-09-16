# 后端架构

`backend/start_all.py` 初始化 `database/sqlite/example_db.db`，随后按顺序启动 9 个服务目录对应的 10 个进程（`services/review_service/` 另有 `scheduler.py`，端口 8086）和 API 网关。API 网关位于 `backend/api_gateway/`，其他服务各自位于 `backend/services/<service_name>/`，共享基础设施位于 `backend/shared/`。

正式提交链路为：OCR 结构化识别 -> 知识图谱匹配题目与标准答案 -> 判题 -> 错因 -> 知识讲解 -> 教学反馈 -> 状态与复习。前端独立运行，网关不托管静态文件。

本目录下的 `api/`、`contracts/` 和 `state-machine/` 保存的是最初的设计稿（含已取消的抄袭判定、苏格拉底引导和固定 Day1/Day3/Day7 复习计划），不代表当前实现；现状请读 `docs/项目完整工作流.md` 与各服务的 `docs/README.md`。

执行 `python backend/start_all.py` 启动后端，执行 `python -m pytest backend/tests -q` 运行回归测试。
