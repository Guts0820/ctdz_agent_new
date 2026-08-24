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

前端继续访问网关的 `/api/v1/teacher/...`，网关会转发到本服务。标准答案导入和题目录入预览均不保存图片文件，只在请求内存中转发图片字节。

本地交互测试：

```powershell
python backend\tools\manual_checks\interactive_standard_answer_upload.py
```

输入图片绝对路径后，脚本会输出导入结果 JSON；输入 `exit` 退出。
