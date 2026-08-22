# 前端说明

`frontend/` 是无需构建的静态网页，通过 `http://127.0.0.1:8000/api` 调用后端。`index.html` 是入口，`js/api.js` 封装请求，`js/student.js`、`teacher.js` 和 `admin.js` 分别负责角色页面。

在本目录执行 `python -m http.server 3000`，访问 `http://127.0.0.1:3000`。学生图片通过 `8000` 网关提交，OCR 置信度低于 0.80 时提示重新上传，一轮最多重传三次；题干、作答或人工复核问题会显示对应原因。

学生拍照错答结果和错题本均通过真实 `mistake_case_id` 打开订正弹窗，调用网关 `/api/v1/mistakes/{mistake_case_id}/correction` 判定新答案；页面不再包含固定演示题或前端硬编码答案。
