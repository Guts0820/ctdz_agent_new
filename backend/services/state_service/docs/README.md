# State Service

学习状态服务监听 `8085`，保留主链需要的学习状态兼容接口。掌握度更新通过 HTTP 委托给 Review Service 的统一 Mastery + Priority 模型；复习生成委托给 Review Service 的按学生、按日期每日计划，不再维护独立公式或固定 Day1/Day3/Day7 计划。

- `POST /internal/api/v1/state/update`：输入本次判题以及 `answer_history_id`、`mistake_case_id`，返回 0-1 的兼容字段 `master_level`、0-100 的 `mastery` 与 `priority`、计算分量和公式版本。
- `POST /internal/api/v1/state/generate-review`：返回 Review Service 当日的幂等计划。
- `GET /internal/api/v1/state/mastery/{student_id}`：从统一 SQLite 掌握度读模型查询结果。

入口：`python -m backend.services.state_service.main`。
