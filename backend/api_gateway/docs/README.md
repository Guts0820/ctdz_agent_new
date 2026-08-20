# API Gateway

API 网关监听 `8000`，向独立前端提供 `/api` 接口，并编排 OCR、知识图谱、判题、错因、知识、教学、教师端、状态和复习服务。教师作业批次和标准答案上传接口由网关转发至 `teacher_service:8090`；前端静态资源不再由网关挂载。

入口：`python -m backend.api_gateway.app`。

`POST /api/v1/submit` 的错答分支固定按“判题 → 错因 → 知识 → 频控 → 状态 → 教学 → 复习计划”执行。错因无法确定知识点返回 `422`，资源不存在返回 `404`，下游不可用返回 `503`，响应结构非法返回 `502`；不得用默认知识点或模板知识内容伪装成功。`answer_history_id`、`mistake_case_id` 会贯穿错因和教学持久化。正确答案只更新学习状态，不调用错因、知识或教学服务。

`POST /api/v1/mistakes/{mistake_case_id}/correction` 接收原题和新答案，复用标准答案判题服务，写入 `answer_history.submit_type=错题订正`。答错时错题保持 `correcting` 并允许再次订正；答对时变为 `corrected`。响应包含订正判定、错题状态、Mastery 对应的教学模式/难度及状态同步结果。
