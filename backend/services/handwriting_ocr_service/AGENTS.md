# Repository Guidelines

## 模块定位

本模块提供图片到结构化判题输入的独立 FastAPI 服务。默认使用云端 `qwen-3.7plus` 多模态模型识别题目、学生作答、公式和图文语义，并生成题目说明；它不判断学生答案正误。

## 架构

`app/main.py` 接收图片并在工作线程调用识别引擎，支持默认的 `student_work` 和教师端的 `standard_answer` 模式。`qwen_vision.py` 将图片编码为数据 URI 请求 Qwen，`schemas.py` 用 Pydantic 生成 JSON Schema、再用 `jsonschema` 校验模型结果。通过校验的 `analysis_input` 才会返回给上层服务；标准答案模式返回按题目分离的 `questions` 数组，同时保留 Markdown 等兼容字段。`OCR_ENGINE=paddleocr_vl` 时使用本地 PaddleOCR-VL。

## 目录结构

- `app/main.py`：HTTP 入口、环境文件加载与健康检查。
- `app/schemas.py`：下游判题契约和 JSON Schema 校验。
- `app/services/qwen_vision.py`：Qwen 多模态适配。
- `app/services/paddleocr_vl.py`：可选本地识别引擎。
- `interactive_ocr.py`：本地输入图片路径的交互入口，终端输出已校验的 `analysis_input`。
- `tests/`：无模型、无网络的单元测试。
- `.env.example`：非敏感配置模板；`docs/README.md`：运行与契约说明。

## 开发规范

使用 Python、四空格缩进、类型标注和 `snake_case`。`OCR_ENGINE` 默认 `qwen`；`QWEN_API_KEY`、`QWEN_BASE_URL` 和 `QWEN_MODEL` 从环境读取，模型默认 `qwen-3.7plus`。云端 HTTP 默认直连，不使用系统代理。`question.text` 只保留原题，排除草稿、批注、箭头和作答；无法与笔记可靠分离时题干与说明置空并将 `review_required` 设为 `true`。`student_answer.text` 只保留未涂改、完整可辨的最终作答；无法确认时置空并复核。未经 JSON Schema 校验的模型内容不得传给下游。`OCR_RUNTIME_ENV=development` 默认 CPU，`production` 默认 GPU；设备变量只影响 Paddle 模式。不得记录图片、密钥或完整识别内容。

## 常用命令

从仓库根目录执行 `python -m pip install -r backend\services\handwriting_ocr_service\requirements.txt` 安装依赖；复制本目录 `.env.example` 为 `.env` 后设置 `QWEN_API_KEY`。OCR 不读取 `backend/.env`。进入本目录运行 `python -m pytest tests -q`；启动使用 `python -m uvicorn app.main:app --port 8089 --workers 1`；交互识别使用 `python interactive_ocr.py`。

## 修改指南

修改 Qwen 提示词、JSON Schema 或 `analysis_input` 时，先补充有效与无效响应测试，并同步检查判题服务和教师标准答案服务的消费逻辑。保留 `markdown`、`confidence`、`engine`、`fallback_used` 和 `status` 字段兼容性。图文题需将视觉语义填入 `question.visual_context`，而不是混入题干文本。
