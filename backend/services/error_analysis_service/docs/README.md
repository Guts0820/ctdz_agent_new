# Error Analysis Service

错因分析服务监听 `8082`，把判题结果转换成错因标签、知识范围、推理说明和总置信度。网关通过内部 API 调用本服务。

入口：`python -m backend.services.error_analysis_service.main`。
