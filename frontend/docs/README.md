# 前端说明

`frontend/` 是无需构建的静态网页，通过 `http://127.0.0.1:8000/api` 调用后端。`index.html` 是入口，`js/api.js` 封装请求，`js/student.js`、`teacher.js` 和 `admin.js` 分别负责角色页面。

在本目录执行 `python -m http.server 3000`，访问 `http://127.0.0.1:3000`。OCR 上传仍直连 `8089`，低于 0.95 的结果提示重新上传，一轮最多重传三次。
