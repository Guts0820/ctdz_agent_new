# 小学生数学知识图谱 API

## 项目概述

本项目提供小学生数学知识图谱的后端API服务，支持知识点查询、题目推荐、错因分析等功能，为前端应用和Trae Agent提供数据接口。

## 技术栈

- **框架**: FastAPI 0.104.1
- **数据库**: Neo4j 5.x
- **语言**: Python 3.11+
- **服务器**: Uvicorn

## 快速开始

### 环境要求

1. Python 3.11+
2. Neo4j Desktop（已配置并运行 `MathKnowledgeGraph` 数据库）

### 安装依赖

```bash
cd backend
pip install --user -r requirements.txt
```

### 配置连接

编辑 `.env` 文件，确保Neo4j连接信息正确：

```env
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=SRIBD123
NEO4J_DATABASE=neo4j

API_HOST=0.0.0.0
API_PORT=8000
```

### 启动服务

```bash
python main.py
```

服务启动后访问：
- **服务地址**: http://localhost:8000
- **交互式文档**: http://localhost:8000/docs
- **API文档**: http://localhost:8000/redoc

## API接口文档

### 基础信息

| 项目 | 值 |
|------|-----|
| 基础URL | http://localhost:8000 |
| 认证方式 | 无需认证 |
| 请求格式 | JSON |
| 响应格式 | JSON |

### 1. 健康检查

```
GET /health
```

**响应示例**:
```json
{
  "status": "healthy",
  "neo4j": "connected",
  "node_count": 1081
}
```

### 2. 数据统计

```
GET /stats
```

**响应示例**:
```json
{
  "nodes": [
    {"label": "['KnowledgePoint']", "count": 256},
    {"label": "['Question']", "count": 747},
    {"label": "['ErrorCause']", "count": 77}
  ],
  "relationships": [
    {"type": "EXAMINES", "count": 747},
    {"type": "IS_A", "count": 248},
    {"type": "RELATED_TO", "count": 101}
  ]
}
```

### 3. 知识点查询

#### 3.1 查询知识点列表

```
GET /api/knowledge_points
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| grade | int | 否 | 年级筛选（1-6） |
| semester | string | 否 | 学期筛选（上册/下册） |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20 |

**请求示例**:
```
GET /api/knowledge_points?grade=3&page=1&page_size=10
```

**响应示例**:
```json
{
  "data": [
    {
      "id": "K001",
      "title": "两位数乘一位数的口算方法",
      "description": "知识点描述",
      "grade": 3,
      "semester": "上册",
      "content": "知识点详细内容",
      "key_formulas": "相关公式",
      "common_mistakes": "常见错误",
      "teaching_points": "教学要点"
    }
  ],
  "total": 256
}
```

#### 3.2 查询单个知识点

```
GET /api/knowledge_points/{knowledge_id}
```

**请求示例**:
```
GET /api/knowledge_points/K001
```

#### 3.3 获取知识点层级树

```
GET /api/knowledge_hierarchy
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| grade | int | 否 | 按年级筛选 |

**响应示例**:
```json
[
  {
    "id": "K001",
    "title": "数的认识",
    "grade": 1,
    "children": [
      {
        "id": "K002",
        "title": "10以内数的认识",
        "grade": 1,
        "children": []
      }
    ]
  }
]
```

### 4. 题目查询

#### 4.1 查询题目列表

```
GET /api/questions
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| grade | int | 否 | 年级筛选 |
| semester | string | 否 | 学期筛选 |
| difficulty | int | 否 | 难度筛选（1-3） |
| knowledge_id | string | 否 | 知识点ID筛选 |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20 |

**请求示例**:
```
GET /api/questions?grade=3&difficulty=2&page=1&page_size=5
```

**响应示例**:
```json
{
  "data": [
    {
      "id": "Q0001",
      "text": "小明有5个苹果，小红有4个苹果，谁的多？",
      "answer": "小明",
      "difficulty": 2,
      "grade": 3,
      "semester": "上册",
      "source": "教材",
      "knowledge_id": "K002",
      "type": "text",
      "image_path": null,
      "answer_steps": "5 > 4，所以小明多"
    }
  ],
  "total": 747
}
```

#### 4.2 查询单个题目

```
GET /api/questions/{question_id}
```

**请求示例**:
```
GET /api/questions/Q0001
```

### 5. 题目推荐

```
POST /api/recommend
```

**请求体**:
```json
{
  "knowledge_ids": ["K001", "K002"],
  "count": 5,
  "difficulty": null
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| knowledge_ids | array | 是 | 知识点ID列表 |
| count | int | 否 | 推荐题目数量，默认5 |
| difficulty | string | 否 | 难度筛选 |

**响应示例**:
```json
{
  "recommended_questions": [
    {
      "id": "Q0001",
      "text": "题目内容",
      "answer": "答案",
      "difficulty": 2,
      "knowledge_id": "K001"
    }
  ],
  "related_knowledge_points": [
    {
      "id": "K003",
      "title": "相关知识点",
      "description": "描述"
    }
  ]
}
```

### 6. 错因查询

#### 6.1 查询错因列表

```
GET /api/error_causes
```

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| grade_range | string | 否 | 年级范围筛选 |
| level1 | string | 否 | 一级分类筛选 |
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20 |

**响应示例**:
```json
{
  "data": [
    {
      "id": "E001",
      "level1": "计算错误",
      "level2": "乘法口诀错误",
      "level3": "记错乘法口诀",
      "criteria": "判断标准",
      "grade_range": "1-3年级",
      "knowledge_scope": "乘法运算",
      "example": "把'三四十二'记成'三四一十三'",
      "name": "错因名称"
    }
  ],
  "total": 77
}
```

#### 6.2 查询单个错因

```
GET /api/error_causes/{error_cause_id}
```

### 7. 错题分析

```
POST /api/analyze
```

**请求体**:
```json
{
  "question_ids": ["Q0001", "Q0003", "Q0005"],
  "knowledge_ids": null
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question_ids | array | 是 | 错题ID列表 |
| knowledge_ids | array | 否 | 知识点ID列表（可选） |

**响应示例**:
```json
{
  "weak_knowledge_points": [
    {
      "knowledge_id": "K002",
      "title": "两位数乘一位数",
      "error_count": 3,
      "related_questions_count": 25
    }
  ],
  "recommended_review_plan": [
    "重点复习知识点：两位数乘一位数 (ID: K002)",
    "该知识点共做错 3 道题"
  ]
}
```

## 使用示例

### Python调用示例

```python
import requests

BASE_URL = "http://localhost:8000"

# 查询知识点
response = requests.get(f"{BASE_URL}/api/knowledge_points", params={
    "grade": 3,
    "page": 1,
    "page_size": 10
})
print(response.json())

# 推荐题目
response = requests.post(f"{BASE_URL}/api/recommend", json={
    "knowledge_ids": ["K001", "K002"],
    "count": 5
})
print(response.json())

# 分析错题
response = requests.post(f"{BASE_URL}/api/analyze", json={
    "question_ids": ["Q0001", "Q0003"]
})
print(response.json())
```

### JavaScript调用示例

```javascript
const BASE_URL = "http://localhost:8000";

// 查询知识点
async function getKnowledgePoints(grade) {
    const response = await fetch(`${BASE_URL}/api/knowledge_points?grade=${grade}&page=1&page_size=10`);
    return await response.json();
}

// 推荐题目
async function recommendQuestions(knowledgeIds, count = 5) {
    const response = await fetch(`${BASE_URL}/api/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_ids: knowledgeIds, count })
    });
    return await response.json();
}

// 分析错题
async function analyzeMistakes(questionIds) {
    const response = await fetch(`${BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_ids: questionIds })
    });
    return await response.json();
}
```

## 数据结构

### KnowledgePoint（知识点）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 知识点唯一ID |
| title | string | 知识点标题 |
| description | string | 知识点描述 |
| grade | int | 年级 |
| semester | string | 学期 |
| content | string | 详细内容 |
| key_formulas | string | 关键公式 |
| common_mistakes | string | 常见错误 |
| teaching_points | string | 教学要点 |

### Question（题目）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 题目唯一ID |
| text | string | 题目内容 |
| answer | string | 答案 |
| difficulty | int | 难度（1-3） |
| grade | int | 年级 |
| semester | string | 学期 |
| source | string | 来源 |
| knowledge_id | string | 关联知识点ID |
| type | string | 类型（text/image） |
| image_path | string | 图片路径 |
| answer_steps | string | 解题步骤 |

### ErrorCause（错因）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 错因唯一ID |
| level1 | string | 一级分类 |
| level2 | string | 二级分类 |
| level3 | string | 三级分类 |
| criteria | string | 判断标准 |
| grade_range | string | 适用年级范围 |
| knowledge_scope | string | 适用知识点范围 |
| example | string | 示例 |
| name | string | 名称 |

## 注意事项

1. **Neo4j必须运行**: 启动API前确保Neo4j Desktop中的 `MathKnowledgeGraph` 数据库已启动
2. **连接配置**: 如果Neo4j密码或端口有变化，请修改 `.env` 文件
3. **CORS**: API已配置允许所有来源跨域请求，生产环境建议限制来源
4. **分页**: 列表接口默认返回20条数据，建议使用分页参数控制返回量
5. **编码**: 所有接口支持中文，使用UTF-8编码

## 项目结构

```
backend/
├── main.py              # 主应用入口
├── database.py          # Neo4j数据库连接
├── models.py            # Pydantic数据模型
├── .env                 # 环境配置
├── requirements.txt     # 依赖列表
└── routers/
    ├── knowledge_points.py   # 知识点接口
    ├── questions.py          # 题目接口
    └── error_causes.py       # 错因接口
```

## 常见问题

### Q: 连接Neo4j失败？

A: 请检查：
1. Neo4j数据库是否已启动
2. `.env` 文件中的密码是否正确
3. 网络连接是否正常（尝试访问 http://localhost:7474 验证）

### Q: 接口返回中文乱码？

A: 确保请求头包含 `Accept: application/json`，API默认返回UTF-8编码。

### Q: 如何扩展新接口？

A: 在 `routers/` 目录下创建新的路由文件，然后在 `main.py` 中注册路由。

## 联系信息

如有问题或需要帮助，请联系项目负责人。