# Analysis Service

判题服务监听 `8081`，接收 OCR 题干和学生答案。没有携带标准答案时，服务通过知识图谱服务召回候选题，由本模块 LLM 重排序；匹配置信度或候选间隔不足时返回 422，不进入判题。确认题目后，从图谱取标准答案和标准步骤，再由 LLM 判断正误。

## LLM 配置

复制 `analysis_service/.env.example` 为同目录 `.env`，设置 `ANALYSIS_LLM_API_KEY`；可按需修改 `ANALYSIS_LLM_BASE_URL`、`ANALYSIS_LLM_MODEL` 和超时。该服务不读取 `backend/.env` 的 LLM 密钥。

LLM 必须返回受限 JSON：`judge_result` 只能是 `correct`、`wrong` 或 `unknown`，并且必须包含反馈、错误步骤、漏缺步骤、错误类型和 0 到 1 的 `confidence`。服务会再次校验响应；未配置密钥、网络失败或格式非法时，回退为答案归一化比较。

Qwen 请求默认直连，不读取系统 `HTTP_PROXY` 或 `HTTPS_PROXY`。

题目匹配还要求返回 `question_id`、`confidence` 和 `runner_up_confidence`。默认要求第一名置信度至少 `0.90`，且领先第二名至少 `0.10`；可通过本模块 `.env` 调整。

## 运行

```powershell
python -m backend.services.analysis_service.main
python -m pytest backend/tests/test_standard_answer_judging.py -q
```
