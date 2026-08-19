# Error Analysis Service

错因分析服务监听 `8082`，把判题结果转换成错因标签、知识范围、推理说明和总置信度。网关通过内部 API 调用本服务。

入口：`python -m backend.services.error_analysis_service.main`。

## 接口

- `POST /internal/api/v1/error-analysis/analyze`：接收完整判题结果，返回三级错因、关联知识点、分析理由和置信度。
- `POST /internal/api/v1/error-analysis/analyze-light`：仅有最终答案时使用的保守分析接口。

服务端只接受 `error_bank` 中存在的错因 ID，并使用题库中的一级、二级、三级名称覆盖模型回传的分类文本。`total_confidence` 和每个标签的 `confidence` 均限制在 `0~1`；低于 `0.7` 时返回 `low_confidence=true`。LLM 不可用或结果不合法时使用规则降级，并标记 `fallback_used=true`。
