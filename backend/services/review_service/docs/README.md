# Review Service

复习服务由 `main.py`（8087）和 `scheduler.py`（8086）组成，涵盖计划、会话、订正、优先级、掌握度与学习统计。数据统一存放在根目录 `database/sqlite/`。

Mastery + Priority 使用 `answer_history` 主链作答以及 `review2_attempt` 复习/订正记录的累计对错、最近作答时间和错因类型作为证据。`POST /priority-runs/internal/mastery-update` 由 State Service 调用，计算后统一写入 `knowledge_mastery`；`POST /review-plans` 根据同一优先级快照生成每日计划。`master_level` 保持 0-1 兼容，`mastery` 和 `priority` 使用 0-100。

复习订正写入 `review2_attempt.correction_*` 后会立即刷新题目关联知识点的 Mastery/Priority，并使学生当天的 Priority 快照失效。

入口：`python -m backend.services.review_service.main`。
