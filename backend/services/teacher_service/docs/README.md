# 教师端服务

教师端服务默认监听 `8090`，当前提供作业批次管理：

- `POST /internal/api/v1/teacher/homework_batch`：创建锁定状态的作业批次。
- `POST /internal/api/v1/teacher/homework_batch/{batch_id}/release`：放行整个批次。
- `POST /internal/api/v1/teacher/homework_batch/{batch_id}/release_partial`：按题目 ID 部分放行。
- `GET /health`：服务健康检查。

标准答案导入：

- `POST /internal/api/v1/teacher/standard_answers`：接收 `image` multipart 文件，调用 OCR 的 `mode=standard_answer`。
- OCR 返回多题数组后逐题写入知识图谱；只保存 `question.text`、`question.explanation` 和 `student_answer.text`。
- 图谱字段映射为 `Question.text`、`Question.explanation`/`Question.answer_steps` 和 `Question.answer`。
- OCR 置信度低于 `0.95` 或要求复核时拒绝写入。

题目录入预览（阶段 A）：

- `POST /internal/api/v1/teacher/question-imports/preview`：接收 `image`、`teacher_id`、`grade` 和可选 `semester`。
- 预览先执行严格标准答案 OCR，再对新题调用一次共享 Qwen 文本模型独立解题；已有 `ready` 题目复用题库答案和步骤。
- 教师答案与系统解答先做确定性数学等价判断，无法确定时才调用受限 LLM 比较器。
- 结果写入 `teacher_question_import` 和 `teacher_question_import_item` 暂存表，状态为 `review_required`，不会写入正式题库。
- 相同教师、年级、学期和图片在 24 小时内重复请求时复用已有预览，避免重复 OCR 和解题调用。
- 单题 LLM 失败不会丢弃 OCR 教师答案，该题标记为 `llm_failed`，留待教师人工确认。

教师裁决与正式入库（阶段 B）：

- `POST /internal/api/v1/teacher/question-imports/{import_id}/confirm`：接收会话内每道题的 `teacher`、`llm`、`existing` 或 `skip` 裁决。
- 服务校验会话所有权、有效期和完整逐题裁决；确认期间状态为 `confirming`，成功后变为 `confirmed`。
- `teacher` 和 `llm` 裁决通过知识图谱内部接口按指纹幂等写入，并保存年级、学期、答案来源、录入教师和 LLM 审计字段。
- `existing` 只复用预览命中的正式 `question_id`，不会覆盖既有答案；`skip` 不写正式题库。

教师题库查询：`GET /internal/api/v1/teacher/questions?teacher_id=T001&grade=3&semester=上学期&page=1&page_size=20&keyword=`。该接口从统一题库读取并只返回 `status=ready` 且 `standard_solution_status=ready` 的共享题目；`teacher_id` 用于请求上下文和审计，不限制题目可见范围。统一题库不可用时返回明确的 503 错误。
- 重复确认已完成的会话直接返回首次结果，不会再次写图谱或调用 LLM；过期会话返回 HTTP 410。

前端继续访问网关的 `/api/v1/teacher/...`，网关会转发到本服务。标准答案导入和题目录入预览均不保存图片文件，只在请求内存中转发图片字节。

本地交互测试：

```powershell
python backend\tools\manual_checks\interactive_standard_answer_upload.py
```

输入图片绝对路径后，脚本会输出导入结果 JSON；输入 `exit` 退出。
