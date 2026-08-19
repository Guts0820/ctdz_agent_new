# API Gateway

API 网关监听 `8000`，向独立前端提供 `/api` 接口，并编排 OCR、知识图谱、判题、错因、知识、教学、教师端、状态和复习服务。教师作业批次和标准答案上传接口由网关转发至 `teacher_service:8090`；前端静态资源不再由网关挂载。

入口：`python -m backend.api_gateway.app`。
