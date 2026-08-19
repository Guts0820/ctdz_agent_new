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

前端继续访问网关的 `/api/v1/teacher/...`，网关会转发到本服务。标准答案导入不保存图片文件，只在请求内存中转发图片字节。

本地交互测试：

```powershell
python backend\tools\manual_checks\interactive_standard_answer_upload.py
```

输入图片绝对路径后，脚本会输出导入结果 JSON；输入 `exit` 退出。
