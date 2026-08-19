# Teaching Service

教学服务监听 `8084`，将错因分析结果转换为讲解、分步引导、提示和练习题，并提供知识点推送频控接口。

入口：`python -m backend.services.teaching_service.main`。

`POST /internal/api/v1/teaching/generate` 按掌握度选择 `BASIC`（<0.4）、`STANDARD`（0.4-0.8）或 `ADVANCED`（>0.8），分别检索 easy、medium、hard 题库候选。LLM 输出经过字段和内容校验；模型失败时使用不伪造答案的模板，并返回 `fallback_used`、`fallback_reason`。题库为空或候选缺少答案/解析时返回空 `practice_list` 与 `practice_fallback_reason`。
