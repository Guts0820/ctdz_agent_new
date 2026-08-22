# 手写 OCR 服务文档

## 定位

本模块在 `:8089` 提供图片到结构化判题输入的识别服务。默认使用云端 `qwen-3.7plus` 多模态模型识别题目、学生作答、公式及图文语义，并生成题目说明；不判断学生答案正误。

## 结构

- `app/main.py`：FastAPI 入口和环境加载。
- `app/services/qwen_vision.py`：Qwen 图片请求、JSON 解析和错误处理。
- `app/schemas.py`：下游 `analysis_input` 契约与 JSON Schema 校验。
- `app/services/paddleocr_vl.py`：可选本地 PaddleOCR-VL 引擎。
- `tests/`：无需真实模型或网络的自动化测试。

## 环境与运行

复制 `.env.example` 为本模块的 `.env` 并设置 `QWEN_API_KEY`。OCR 服务不会读取 `backend/.env`，两者的密钥配置相互隔离。默认配置：

```env
OCR_ENGINE=qwen
QWEN_MODEL=qwen-3.7plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

OCR 发往 Qwen 的 HTTP 请求默认直连，不使用系统 `HTTP_PROXY` 或 `HTTPS_PROXY`。

统一联调时使用仓库的 Python 3.11 虚拟环境：

```powershell
D:\ctdz_agent_venv\Scripts\python.exe -m pip install -r requirements.txt
D:\ctdz_agent_venv\Scripts\python.exe -m pytest tests -q
D:\ctdz_agent_venv\Scripts\python.exe -m uvicorn app.main:app --port 8089 --workers 1
```

`OCR_ENGINE=paddleocr_vl` 可切换到本地引擎。本地开发的 `OCR_RUNTIME_ENV=development` 默认 CPU，服务部署使用 `production` 默认 GPU；设备配置只影响 Paddle 模式。

## 本地交互识别

运行 `..\.venv311\Scripts\python.exe interactive_ocr.py`，输入图片绝对路径；输入 `exit` 结束。每次识别会在 `recognition_results/` 保留兼容 Markdown 和完整响应 JSON，同时在终端直接显示通过 JSON Schema 校验的 `analysis_input`，供判题模块使用。

## 下游契约

`POST /v1/recognize` 接收 `image` 文件和可选 `mode` 表单字段。默认 `mode=student_work`，保留 `markdown`、`confidence`、`engine` 和 `status` 兼容字段，并返回通过 JSON Schema 校验的单题 `analysis_input`。

教师标准答案上传使用 `mode=standard_answer`，返回的 `analysis_input` 为按题目分离的数组：

```json
{
  "schema_version": "1.0",
  "questions": [
    {
      "question": {"text": "1+1=", "explanation": "求和。", "visual_context": []},
      "student_answer": {"text": "2"}
    }
  ],
  "confidence": 0.99,
  "review_required": false
}
```

默认判题模式的结构为：

```json
{
  "schema_version": "1.0",
  "question": {
    "text": "题干",
    "explanation": "已知条件与求解目标",
    "visual_context": [{"kind": "diagram", "description": "图形语义"}]
  },
  "student_answer": {"text": "学生作答"},
  "confidence": 0.94,
  "review_required": false
}
```

网关应使用该对象的题干、作答、说明和视觉语义；不得消费调试字段 `raw_json`。当 `review_required=true` 或状态为 `low_confidence` 时，应先让用户确认识别内容。学生作业由网关以 `0.80` 为质量门槛，教师标准答案上传仍以 `0.95` 为门槛。本服务返回实际置信度，网关负责阻止不合格结果进入判题，并把通过校验的题干交给后续流程。OCR 服务不判断答案正误。

`student_answer.text` 仅保留未涂改、完整可辨的最终答案；划掉、覆盖或删除的旧答案不得拼接进去。例如作答栏里有被划掉的 `740` 和清晰的 `7950` 时，返回 `7950`。若不存在可确认的最终答案，该字段为空字符串且 `review_required=true`。

`question.text` 仅保留原题的完整文字、公式和图形条件，不能混入草稿计算、旁注、批注、箭头、圈画、改写或学生作答，也不能用笔记中的数字补全题干。原题本身为手写时，应通过题号、对齐和作答区分隔判断，不可仅按字体删除。若题干与笔记无法可靠分离，`question.text` 与 `question.explanation` 均为空字符串，且 `review_required=true`；上层应要求用户确认，不得判题。
