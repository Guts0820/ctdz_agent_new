# 静态前端模块说明

## 模块定位

本模块是小学数学错题订正系统的独立浏览器界面，无需打包构建，通过 HTTP 调用 `:8000` API 网关。

## 架构

`index.html` 引入 Tailwind CSS 和 Chart.js CDN 资源，以及 `js/` 下的脚本。`app.js` 管理视图，`login.js` 基于 Mock 数据处理登录，学生、教师和管理员页面分别由对应脚本渲染；`api.js` 以 `http://127.0.0.1:8000/api` 封装后端调用。部分功能仍使用 `mock-data.js`，OCR 上传直连 `:8089`。

## 目录结构

- `index.html`：单页应用入口和样式。
- `js/api.js`：后端 API 调用封装。
- `js/app.js`、`login.js`：应用控制和登录。
- `js/student.js`、`teacher.js`、`admin.js`：角色页面逻辑。
- `js/mock-data.js`：演示/未接入功能的本地数据。
- `启动Demo.bat`：Windows 静态服务启动脚本。
- `docs/README.md`：当前前端说明与数据边界。

## 开发规范

使用原生 HTML、CSS 和 JavaScript，保持现有全局对象与函数命名风格。OCR 上传使用 `OcrUploadPolicy`：置信度必须达到 `0.95`，低于阈值提示“照片模糊，请重新上传”，初次上传失败后最多重传三次；低置信或服务失败不得显示模拟判题结果。API 失败必须有用户可理解的处理；不要将密钥、真实学生数据或服务端连接凭据放入前端。使用 CDN 的资源变更需考虑在线依赖；提交前避免把纯演示 Mock 误接入真实业务流程。

## 常用命令

在本目录执行 `python -m http.server 3000` 启动静态服务器，或双击 `启动Demo.bat`。运行 `node --test tests\ocr-upload-policy.test.js` 验证 OCR 上传阈值和重传上限。完整联调从仓库根目录执行 `python backend\start_all.py`，前端独立启动后访问 `http://127.0.0.1:3000/`。

## 修改指南

更改 API 路径或响应字段时同步修改 `js/api.js`、对应页面和主网关。页面需验证学生、教师、管理员三种角色；调整 OCR 流程还应验证上传失败、识别失败和服务未启动的提示。不要将 Mock 数据的存在误报为真实后端能力。
