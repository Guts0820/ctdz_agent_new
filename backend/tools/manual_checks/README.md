# 手工联调工具

## 图片判题链路

`interactive_image_judging.py` 通过 API Gateway 联调完整链路：图片编码、OCR、知识图谱题目精确匹配、标准答案判题。

先启动 Neo4j 和后端服务，再从项目根目录执行：

```powershell
python backend/tools/manual_checks/interactive_image_judging.py
```

输入图片绝对路径，输入 `exit` 结束。脚本只输出 `正确`、`错误` 或无法判定信息；若 OCR 题干未与知识图谱题目完全匹配，会显示网关返回的“无法匹配知识图谱中的标准题目”提示。

默认网关是 `http://127.0.0.1:8000`，默认学生 ID 是 `interactive-test-student`。可用环境变量 `API_GATEWAY_URL` 和 `STUDENT_ID` 覆盖。图片仅在内存中编码并提交，不会由脚本保存。
