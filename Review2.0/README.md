# 小学生数学知识图谱 - 后端服务

## 1. 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.104.1 |
| ASGI 服务器 | Uvicorn | 0.24.0 |
| 图数据库 | Neo4j | 5.x |
| 关系数据库 | SQLite | - |
| 数据校验 | Pydantic | 2.5.2 |
| Python | - | 3.11+ |

## 2. 快速启动

### 步骤一：安装 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

### 步骤二：安装 & 启动 Neo4j

1. 下载 Neo4j Community Edition（5.x）：https://neo4j.com/download/
2. 解压后进入目录，启动数据库：
   ```bash
   # Windows
   bin\neo4j-console.bat
   # Linux/Mac
   bin/neo4j console
   ```
3. 浏览器访问 http://localhost:7474，首次登录后修改默认密码

### 步骤三：修改配置

编辑 `.env` 文件（根据实际环境调整）：

```env
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=你的Neo4j密码
NEO4J_DATABASE=neo4j

API_HOST=0.0.0.0
API_PORT=8000
```

### 步骤四：导入知识图谱数据（首次部署需要）

如果是空的 Neo4j 数据库，需要先导入数据。数据文件位于项目根目录的知识图谱数据文件夹中：

```bash
# 方式一：使用浏览器界面 http://localhost:7474 手动 CSV 导入
# 方式二：使用已有的数据导入脚本
python import_new_data.py
```

> 如果从同事处获取的已配置好的数据库，直接启动即可跳过此步。

### 步骤五：启动服务

```bash
# 方式一：直接运行（推荐）
python main.py

# 方式二：uvicorn 启动（支持热重载，开发时使用）
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 步骤六：验证服务

```bash
curl http://localhost:8000/health
# 期望返回: {"status":"healthy","neo4j":"connected","node_count":2901}
```

启动成功后访问：
- API 服务地址: http://localhost:8000
- Swagger 文档: http://localhost:8000/docs
- ReDoc 文档: http://localhost:8000/redoc

## 3. 项目结构

```
backend/
├── main.py                        # ⭐ FastAPI 入口，注册所有路由
├── database.py                    # Neo4j 连接封装（query方法）
├── user_database.py               # SQLite 用户数据库
├── models.py                      # Pydantic 数据模型
├── .env                           # 环境变量配置
├── requirements.txt               # Python 依赖清单
├── user_data.db                   # SQLite 用户数据（首次运行自动创建）
├── learning_data.db               # SQLite 掌握度数据（首次运行自动创建）
│
├── routers/                       # 基础业务路由
│   ├── students.py                #   学生管理（7个接口）
│   ├── knowledge_points.py        #   知识点查询（3个接口）
│   ├── questions.py               #   题目查询与推荐（4个接口）
│   ├── error_causes.py            #   错因分析（2个接口）
│   ├── users.py                   #   用户登录/信息
│   └── growth_report.py           #   成长报告（5个接口）
│
├── mastery/                       # 掌握度计算模块
│   ├── api.py                     #   API 路由（6个接口）
│   ├── calculator.py              #   核心算法（准确率/一致性/保持率/错误控制力）
│   └── database.py                #   数据存储层
│
├── datahub/                       # 数据中心（分层架构）
│   ├── api.py                     #   DataHub API（15+个接口）
│   ├── config.py                  #   模块配置
│   ├── models.py                  #   数据模型
│   ├── core/                      #   核心业务
│   │   ├── learning_path.py       #     🧭 学习路径推荐器
│   │   ├── statistics.py          #     统计报表
│   │   └── aggregator.py          #     数据聚合
│   └── clients/                   #   外部客户端
│       ├── review_plan_client.py  #     复习计划客户端
│       └── error_analysis_client.py #   错因分析客户端
│
└── review/                        # 复习计划引擎（DDD架构）
    ├── config.py                  #   配置
    ├── dependencies.py            #   依赖注入
    ├── api/                       #   API 路由层
    │   ├── priority.py            #     优先级计算
    │   ├── review_plans.py        #     计划管理
    │   ├── review_sessions.py     #     答题会话
    │   └── corrections.py         #     错题订正
    ├── schemas/                   #   数据模型
    │   ├── priority.py            #     优先级请求/响应
    │   └── review.py              #     计划/题目/会话模型
    ├── domain/                    #   领域层
    │   └── enums.py               #     状态枚举
    ├── services/                  #   业务逻辑层
    │   ├── priority_calculator.py #     优先级算法
    │   ├── priority_service.py    #     优先级编排
    │   ├── plan_service.py        #     计划生成
    │   ├── question_selector.py   #     贪心选题
    │   └── session_service.py     #     会话状态机
    ├── integrations/              #   数据集成
    │   ├── contracts.py           #     数据契约接口
    │   └── neo4j_contracts.py     #     Neo4j 适配
    └── repositories/              #   数据仓储
        └── __init__.py
```

## 4. 数据模型

### 4.1 Neo4j 节点（知识图谱）

| 标签 | 主要属性 | 说明 |
|------|----------|------|
| Student | student_id, name, grade, class_name, gender, school | 学生 |
| KnowledgePoint | id, title, description, grade, semester, content | 知识点 |
| Question | id, text, answer, difficulty, grade, knowledge_id | 题目 |
| ErrorCause | id, level1, level2, level3, name, criteria | 错因 |
| AnswerHistory | student_id, is_correct, answered_at | 答题记录 |

### 4.2 Neo4j 关系

| 关系类型 | 说明 |
|----------|------|
| MASTERY | Student → KnowledgePoint（掌握度） |
| EXAMINES | Question → KnowledgePoint（题目考查知识点） |
| PREREQUISITE_OF | KnowledgePoint → KnowledgePoint（前置依赖） |
| ANSWERS_QUESTION | Student → Question（学生答题） |
| FOR_MISTAKE | AnswerHistory → MistakeCase（答题记录关联错题） |
| HAS_ERROR_CAUSE | MistakeCase → ErrorCause（错题关联错因） |

### 4.3 SQLite 表

| 表名 | 说明 |
|------|------|
| user | 用户账号 |
| wrong_question | 错题记录 |
| learning_progress | 学习进度 |
| review_plan | 复习计划 |

## 5. API 接口清单

### 基础接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/stats` | 数据库统计 |

### 学生管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/students/` | 学生列表（支持年级/班级筛选） |
| GET | `/api/students/classes` | 班级列表 |
| GET | `/api/students/{id}` | 学生详情 |
| GET | `/api/students/{id}/mastery` | 学生掌握度 |
| GET | `/api/students/{id}/weak` | 薄弱知识点 |
| GET | `/api/students/class/{name}` | 班级学生 |
| GET | `/api/students/class/{name}/mastery` | 班级掌握度 |

### 知识点 & 题目

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge_points` | 知识点列表 |
| GET | `/api/knowledge_points/{id}` | 知识点详情 |
| GET | `/api/knowledge_hierarchy` | 层级树 |
| GET | `/api/questions` | 题目列表 |
| GET | `/api/questions/{id}` | 题目详情 |
| GET | `/api/questions/{id}/similar` | 相似题目 |
| POST | `/api/recommend` | 推荐题目 |

### 错因分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/error_causes` | 错因列表 |
| POST | `/api/analyze` | 错题分析 |

### 成长报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/growth_report/{id}` | 完整报告 |
| GET | `/api/five_dimension_scores/{id}` | 五维能力 |
| GET | `/api/weak_areas/{id}` | 薄弱领域 |
| GET | `/api/learning_path/{id}` | 学习路径 |

### 掌握度计算

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/mastery/calculate` | 单知识点掌握度 |
| POST | `/api/mastery/five_dimension` | 五维评估 |
| POST | `/api/mastery/add_record` | 添加练习记录 |

### 数据中心 DataHub

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/datahub/statistics/overview` | 系统概览 |
| GET | `/api/datahub/learning_path/{id}` | 学习路径 |
| GET | `/api/datahub/learning_path/{id}/detailed` | 详细路径 |
| GET | `/api/datahub/growth_report/{id}` | 成长报告 |
| GET | `/api/datahub/comprehensive/{id}` | 综合分析 |
| GET | `/api/datahub/mistake_analysis/{id}` | 错题分析 |
| GET | `/api/datahub/knowledge/{id}` | 知识点详情 |
| GET | `/api/datahub/knowledge/{id}/questions` | 知识点题目 |
| POST | `/api/datahub/review_plan/generate` | 生成复习计划 |

### 复习计划引擎

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/priority-runs` | 计算优先级 |
| POST | `/api/review-plans` | 生成计划 |
| GET | `/api/review-plans/{id}` | 计划详情 |
| PATCH | `/api/review-plans/{id}/capacity` | 调整题量 |
| POST | `/api/review-plans/{id}/start` | 启动练习 |
| GET | `/api/review-sessions/{id}` | 会话状态 |
| POST | `/api/review-sessions/{id}/attempts` | 提交答案 |
| POST | `/api/review-sessions/{id}/pause` | 暂停会话 |
| POST | `/api/review-sessions/{id}/resume` | 恢复会话 |
| POST | `/api/attempts/{id}/correction` | 错题订正 |

## 6. 复习计划流程

```
① 计算优先级   POST /api/priority-runs       → 各知识点优先级
② 生成计划     POST /api/review-plans         → plan_id + 题目列表
③ 启动练习     POST /api/review-plans/{id}/start → session_id + 第一题
④ 提交答案     POST /api/review-sessions/{id}/attempts → 对错 + 下一题
⑤ 订正错题     POST /api/attempts/{id}/correction
```

## 7. ID 格式

| 类型 | 格式 | 示例 | 存储位置 |
|------|------|------|----------|
| 学生 | S + 3位数字 | S001 | Neo4j |
| 知识点 | K + 3位数字 | K001 | Neo4j |
| 题目 | Q + 4位数字 | Q0001 | Neo4j |
| 错因 | E + 3位数字 | E001 | Neo4j |
| 用户 | 整数 | 1 | SQLite |

> ⚠️ Neo4j 的 student_id (S001) 和 SQLite 的 user_id (1) 是不同体系，对应关系在 SQLite user 表中。

## 8. 前端调用示例

### JavaScript

```javascript
const API_BASE = 'http://localhost:8000/api';

// 1. 获取班级学生
const r1 = await fetch(`${API_BASE}/students/class/${encodeURIComponent('1年级一班')}`);
const students = (await r1.json()).data;

// 2. 获取学生掌握度
const r2 = await fetch(`${API_BASE}/students/S001/mastery`);
const mastery = (await r2.json()).mastery_data;

// 3. 生成复习计划
const r3 = await fetch(`${API_BASE}/review-plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: 'S001', mode: 'question_count', question_count: 10 })
});
const plan = await r3.json();

// 4. 启动练习
const r4 = await fetch(`${API_BASE}/review-plans/${plan.id}/start`, { method: 'POST' });
const session = await r4.json();

// 5. 提交答案
const r5 = await fetch(`${API_BASE}/review-sessions/${session.session_id}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        question_id: session.current_question.id,
        selected_option: 0,
        time_spent_seconds: 30
    })
});
const result = await r5.json();
console.log('正确:', result.is_correct);
```

### Python

```python
import requests

BASE = "http://localhost:8000/api"

# 获取学生列表
students = requests.get(f"{BASE}/students/").json()["data"]

# 生成复习计划
plan = requests.post(f"{BASE}/review-plans", json={
    "student_id": "S001",
    "mode": "question_count",
    "question_count": 10
}).json()

# 启动练习会话
session = requests.post(f"{BASE}/review-plans/{plan['id']}/start").json()

# 提交答案
result = requests.post(
    f"{BASE}/review-sessions/{session['session_id']}/attempts",
    json={"question_id": session["current_question"]["id"], "selected_option": 0}
).json()
```

## 9. 核心算法

### 9.1 掌握度计算
- **准确率** = 正确数 / 总数
- **一致性** = 答题稳定性（正确率方差）
- **保持率** = 时间衰减掌握程度
- **错误控制力** = 订正率和重复犯错率
- **最终掌握度** = 四维加权综合

### 9.2 优先级计算
综合 5 个因子：技能差距、错误严重度、遗忘风险、知识点重要性、掌握度趋势

### 9.3 贪心选题
根据优先级排序，综合知识点覆盖率、难度匹配、题目去重，选择最优题目组合

## 10. 注意事项

1. **Neo4j 必须先启动**，可访问 http://localhost:7474 验证
2. **图片路径**：题目图片挂载在 `/images/`，物理路径需在 `main.py` 中配置
3. **CORS 已全开**：生产环境建议限制来源
4. **订正功能**：只能在会话完成后才能调用 `/api/attempts/{id}/correction`
5. **Python 版本**：需要 3.11+，推荐使用 conda 环境

## 11. 常见问题

**Q: 启动报 "无法连接 Neo4j"**
A: 检查 Neo4j 服务是否启动，确认 `.env` 中密码是否正确。

**Q: API 返回 500 错误**
A: 查看后端控制台日志，常见原因：Neo4j 数据为空、数据库未导入、代码异常。

**Q: 前端请求报 CORS 错误**
A: 后端已配置 `allow_origins=["*"]`，如果仍有问题，检查后端是否正常运行。

**Q: 图片无法显示**
A: 确认 `main.py` 中的 `IMAGE_DIR` 路径指向正确的图片存储目录。