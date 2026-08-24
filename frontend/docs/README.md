# 前端说明

`frontend/` 是无需构建的静态网页，通过 `http://127.0.0.1:8000/api` 调用后端。`index.html` 是入口，`js/api.js` 封装请求，`js/student.js`、`teacher.js` 和 `admin.js` 分别负责角色页面。

在本目录执行 `python -m http.server 3000`，访问 `http://127.0.0.1:3000`。学生图片通过 `8000` 网关提交，OCR 置信度低于 0.80 时提示重新上传，一轮最多重传三次；题干、作答或人工复核问题会显示对应原因。

学生拍照错答结果和错题本均通过真实 `mistake_case_id` 打开订正弹窗，调用网关 `/api/v1/mistakes/{mistake_case_id}/correction` 判定新答案；页面不再包含固定演示题或前端硬编码答案。

教师作业页提供“录入标准答案题目”入口，支持移动端后置摄像头拍照和本地 JPEG、PNG、WebP、BMP 图片。教师需选择适用年级，可选学期；前端校验 10 MB 大小限制后，以 `multipart/form-data` 调用 `/api/v1/teacher/question-imports/preview`。界面分别展示上传、OCR 和 LLM 复核状态，并在请求期间阻止重复提交。

预览生成后进入逐题复核页。教师可编辑题干和教师答案，查看 LLM 答案、步骤、比较状态和冲突原因，并逐题采用教师答案、LLM 答案、既有题库答案或跳过。冲突和不确定题不设默认裁决，LLM 失败题不能采用 LLM 答案；全部裁决完成后先展示决策汇总，再调用 `/api/v1/teacher/question-imports/{import_id}/confirm` 正式入库。确认响应中的题目 ID 会保留在页面状态中，供后续批次选题联动使用。

批次选题使用教师专用题库接口 `/api/v1/teacher/questions`，仅展示 `ready` 且标准解题为 `ready` 的共享题目，支持年级和题干搜索。题库为空时显示录题提示，加载失败时显示重试，不再把服务异常伪装成空列表；本次确认入库的题目会在打开批次弹窗时自动勾选，未选择题目或题库加载失败时“确认创建”保持禁用。
