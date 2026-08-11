# CTDZ Agent - 后端系统

## 📖 项目概述

CTDZ (Coaching through Deliberate Zooming) Agent 是一个**小学数学智能批改与辅导系统**，采用微服务架构设计。系统能够：

- 📝 自动批改学生作业（支持图片 OCR 和文本输入）
- 🔍 智能分析错误原因（错因标签、知识点映射）
- 📚 提供个性化教学内容（三档教学模式）
- 📊 管理学生知识掌握状态（掌握度计算、复习计划）
- ⏰ 定时调度复习任务（艾宾浩斯遗忘曲线 Day1/Day3/Day7）

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          API Gateway (8000)                              │
│  /api/v1/submit          作业提交入口                                   │
│  /api/v1/student/{id}/mastery  学生掌握度查询                            │
│  /health                 全服务健康检查                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                         服务编排流程                                     │
│  Submit → Analysis → ErrorAnalysis → Knowledge → Teaching → State → Review│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │
│  │ Analysis Service    │  │ Error Analysis      │  │ Knowledge Service │ │
│  │     (8081)          │  │      Agent (8082)   │  │     (8083)        │ │
│  │ 答题分析/OCR/抄袭检测│  │ 错因分析/LLM/知识点映射│  │ 知识点检索/大纲验证│ │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘ │
│                                                                         │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │
│  │ Teaching Service    │  │ State Service       │  │ Review Scheduler │ │
│  │     (8084)          │  │     (8085)          │  │     (8086)       │ │
│  │ 教学生成/频率限制   │  │ 掌握度/复习计划     │  │ 任务调度/推送记录 │ │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘ │
│                                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │  Knowledge Graph    │  │              SQLite Database              │ │
│  │     Service (8007)  │  │     14 Tables: students, knowledge, etc.   │ │
│  │   Neo4j 知识图谱    │  └──────────────────────────────────────────┘ │
│  └─────────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 主要开发语言 |
| 框架 | FastAPI | 高性能 Web 框架 |
| 数据库 | SQLite | 轻量级关系数据库 |
| 知识图谱 | Neo4j | 图数据库（可选） |
| AI 引擎 | 百度千帆 LLM | 错因分析、教学内容生成 |
| OCR | PaddleOCR（可选） | 图片文字识别 |
| 通信 | HTTP/REST | 服务间同步通信 |

---

## 📁 项目结构

```
backend/
├── api_gateway.py              # API 网关（统一入口 + 服务编排）
├── all_in_one.py               # 单体模式（集成所有服务逻辑）
├── start_all.py                # 一键启动所有服务
├── 0804_README.md              # 本文件
│
├── services/                   # 微服务模块
│   ├── analysis_service.py     #   答题分析服务 (8081)
│   ├── error_analysis_agent.py #   错因分析 Agent (8082)
│   ├── knowledge_service.py    #   知识点检索服务 (8083)
│   ├── teaching_service.py     #   教学内容生成服务 (8084)
│   ├── state_service.py        #   状态管理服务 (8085)
│   ├── review_scheduler.py     #   复习调度服务 (8086)
│   ├── mastery_utils.py        #   掌握度计算工具
│   ├── id_utils.py             #   ID 生成工具
│   └── llm_client.py           #   LLM 调用客户端
│
├── database/                   # 数据库相关
│   ├── init_db.py              #   数据库初始化脚本
│   ├── schema.sql              #   表结构定义
│   ├── knowledge_points.csv    #   知识点数据（255+ 条）
│   └── example_db.db           #   SQLite 数据库文件
│
├── logs/                       # 日志目录
│   ├── API_Gateway.log
│   ├── Analysis_Service.log
│   └── ...
│
└── contracts/                  # 接口契约文档
    └── service_contracts.md
```

---

## 🚀 快速开始

### 环境要求

```bash
Python 3.10+
pip install fastapi uvicorn pydantic requests python-dotenv
# 可选：pip install paddleocr  # 启用真实 OCR
```

### 一键启动

```bash
# 方式一：微服务模式（推荐）
cd backend
python start_all.py

# 方式二：单体模式（快速验证）
cd backend
python all_in_one.py
```

### 单独启动服务

```bash
# API 网关
python api_gateway.py          # http://localhost:8000

# 分析服务
python services/analysis_service.py   # http://localhost:8081

# 其他服务...
```

### 测试接口

```bash
# 健康检查
curl http://localhost:8000/health

# 提交作业（文本）
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "S-0001",
    "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
    "student_write": "25+38=53",
    "grade": "三年级"
  }'

# 查询学生掌握度
curl http://localhost:8000/api/v1/student/S-0001/mastery
```

---

## 🔑 核心服务详解

### 1. API 网关 (`api_gateway.py`)

**端口**: 8000 | **职责**: 统一入口、服务编排、请求转发

```python
# 核心编排逻辑（简化）
@app.post("/api/v1/submit")
def submit_homework(request: SubmitRequest):
    # 1. 调用分析服务
    analysis_result = call_analysis_service(request)
    
    # 2. 处理抄袭检测
    if analysis_result["is_copy"]:
        return handle_copy_detection(analysis_result)
    
    # 3. 判定正确/错误
    if analysis_result["judge_result"] == "correct":
        return handle_correct_answer(request, analysis_result)
    
    # 4. 错题处理流程
    error_result = call_error_analysis_service(analysis_result)
    knowledge_result = call_knowledge_service(error_result)
    state_result = call_state_service(request, error_result, is_correct=False)
    teaching_result = call_teaching_service(error_result, state_result)
    
    return build_response(...)
```

**服务配置**:
```python
SERVICE_URLS = {
    "analysis": "http://127.0.0.1:8081",
    "error_analysis": "http://127.0.0.1:8082",
    "knowledge": "http://127.0.0.1:8083",
    "teaching": "http://127.0.0.1:8084",
    "state": "http://127.0.0.1:8085",
    "knowledge_graph": "http://127.0.0.1:8007"
}
```

---

### 2. 答题分析服务 (`analysis_service.py`)

**端口**: 8081 | **职责**: OCR 识别、答案判定、抄袭检测

```python
@app.post("/internal/api/v1/analysis/process")
def process_analysis(request: AnalysisRequest):
    # 1. OCR 识别（模拟/真实）
    ocr_result = simulate_ocr(request)
    
    # 2. 文本解析
    parse_result = simulate_parse(ocr_result)
    
    # 3. 判定处理
    process_result = simulate_process_check(parse_result)
    
    # 4. 持久化
    save_to_history(process_result)
    
    return AnalysisResponse(**process_result)
```

**核心判定逻辑**:
```python
def analyze_steps(question: str, answer: str) -> dict:
    if "25" in question and "38" in question:
        if "63" in answer:
            return {"judge_result": "correct", "step_feedback": "计算正确！"}
        elif "53" in answer:
            return {
                "judge_result": "wrong",
                "step_feedback": "十位计算时忘记加进位的1。",
                "error_step_list": ["十位计算错误：2+3忘记加进位的1"]
            }
```

**抄袭检测**:
```python
def check_plagiarism(answer: str) -> bool:
    standard_answers = ["63", "25+38=63"]
    for std in standard_answers:
        if std in answer and len(answer) <= len(std) + 5:
            return True
    return False
```

---

### 3. 错因分析 Agent (`error_analysis_agent.py`)

**端口**: 8082 | **职责**: 错因标签匹配、LLM 智能分析、知识点映射

**三级错因体系**:
```
计算 → 口算与基本运算 → 进位加法中十位漏加进位1 (C-001)
计算 → 口算与基本运算 → 退位减法中十位漏减退位1 (C-002)
计算 → 竖式计算       → 加法进位标记遗漏 (C-005)
概念 → 定义混淆       → 周长与面积混淆 (K-001)
审题 → 遗漏条件       → 忽略单位换算 (R-001)
粗心 → 抄错数字       → 抄错数字 (M-001)
```

**LLM 分析流程**:
```python
def analyze_error_with_llm(request: ErrorAnalysisRequest):
    # 1. 获取候选错因和知识点
    error_candidates = fetch_candidate_errors()
    knowledge_candidates = fetch_candidate_knowledge()
    
    # 2. 构建 Prompt
    system_prompt = f"""
        你是小学数学错因分析专家。
        候选错因列表：{error_list}
        候选知识点列表：{knowledge_list}
        请输出 JSON 格式分析结果。
    """
    
    # 3. 调用 LLM
    response = call_llm(system_prompt, user_prompt)
    
    # 4. 结果验证
    error_tags = validate_error_tags(parsed, valid_ids)
    knowledge_id = validate_knowledge(parsed, valid_ids)
```

**降级方案**（LLM 调用失败时）:
```python
def match_error_tags(request: ErrorAnalysisRequest) -> List[ErrorTag]:
    if "计算" in core_type:
        if "进位" in step_feedback:
            return [ErrorTag(error_id="C-001", level1="计算", ...)]
    # ...更多规则匹配
```

---

### 4. 知识点检索服务 (`knowledge_service.py`)

**端口**: 8083 | **职责**: 知识点详情、大纲验证、前置/后续关系

```python
@app.post("/internal/api/v1/knowledge/retrieve")
def retrieve_knowledge(request: KnowledgeRetrieveRequest):
    # 1. 从知识图谱获取
    knowledge = fetch_knowledge_from_graph(request.knowledge_id)
    
    # 2. 大纲验证
    if not validate_scope(request, knowledge):
        raise HTTPException(400, "超出教学大纲范围")
    
    return KnowledgeRetrieveResponse(
        knowledge_explanation=knowledge.get("content"),
        difficulty=knowledge.get("difficulty"),
        common_errors=knowledge.get("common_mistakes"),
        teaching_tips=knowledge.get("teaching_points")
    )
```

**年级大纲验证**:
```python
def validate_scope(request, knowledge) -> bool:
    grade_mapping = {
        "三年级": ["一年级", "二年级", "三年级"],
        "四年级": ["一年级", "二年级", "三年级", "四年级"],
        # ...
    }
    return knowledge["grade"] in grade_mapping.get(request.grade, [])
```

---

### 5. 教学内容服务 (`teaching_service.py`)

**端口**: 8084 | **职责**: 三档教学模式、LLM 内容生成、频率限制

**三档教学模式**:
```python
def determine_mode(master_level: float) -> str:
    if master_level < 0.4:
        return "BASIC"      # 基础模式：通俗易懂
    elif master_level < 0.8:
        return "STANDARD"   # 标准模式：方法步骤
    else:
        return "ADVANCED"   # 进阶模式：拓展巩固
```

**LLM 教学生成**:
```python
def generate_teaching_with_llm(request, mode):
    system_prompt = f"""
        你是小学数学老师。
        教学模式：{mode_desc}
        错因：{error_tags}
        请生成 explanation、hints、reasoning_content。
    """
    return call_llm(system_prompt, user_prompt)
```

**频率限制检查**:
```python
def check_frequency(student_id, knowledge_id):
    daily_limit = 5    # 每日推送上限
    weekly_limit = 3   # 每周推送上限
    
    push_permission = (
        daily_count < daily_limit and 
        weekly_count < weekly_limit
    )
```

---

### 6. 状态管理服务 (`state_service.py`)

**端口**: 8085 | **职责**: 掌握度计算、复习计划生成

**掌握度算法** (`mastery_utils.py`):
```python
def calculate_mastery(correct_count: int, wrong_count: int) -> tuple:
    if correct_count >= 2:
        return 1.00, "mastered"      # 连续2次答对 → 已掌握
    elif wrong_count >= 2:
        return 0.00, "weak"          # 连续2次答错 → 薄弱
    elif correct_count == 0 and wrong_count == 0:
        return 0.00, "pending"       # 初始状态
    else:
        total = correct_count + wrong_count
        master_level = (correct_count * 0.5) / total
        return round(master_level, 2), "pending"
```

**复习计划生成**:
```python
def generate_review(student_id, knowledge_id, master_level):
    stage_dates = {
        "Day1": today + timedelta(days=1),
        "Day3": today + timedelta(days=3),
        "Day7": today + timedelta(days=7)
    }
    # 创建复习计划 + 推送记录
    for stage in ["Day1", "Day3", "Day7"]:
        create_review_plan(review_plan_id, stage)
        create_push_record(push_record_id, stage_dates[stage])
```

---

### 7. 复习调度服务 (`review_scheduler.py`)

**端口**: 8086 | **职责**: 定时任务、推送记录管理

```python
@app.get("/internal/api/v1/review/scheduler/run")
def run_scheduler():
    # 查询当日待推送任务
    tasks = query_pending_tasks(today)
    
    # 更新任务状态
    for task in tasks:
        update_status(task["push_record_id"], "pushing")
    
    return {"tasks": tasks}

@app.post("/internal/api/v1/review/scheduler/complete/{id}")
def complete_review_task(push_record_id, is_correct):
    # 更新掌握度
    update_mastery(student_id, knowledge_id, is_correct)
    
    # 掌握 → 完成所有复习
    if mastery_status == "mastered":
        complete_all_plans(review_plan_id)
    # 薄弱 → 取消复习计划
    elif mastery_status == "weak":
        cancel_plan(review_plan_id)
```

**后台定时线程**:
```python
def start_scheduler():
    while True:
        run_scheduler()
        time.sleep(3600)  # 每小时检查一次
```

---

## 🗄️ 数据库设计

### 表结构关系图

```
students ──1:N──→ answer_history
         ──1:N──→ mistake_case
         ──1:N──→ knowledge_mastery
         ──1:N──→ frequency_limit

knowledge ──1:N──→ question_knowledge_mapping
          ──1:N──→ knowledge_mastery

question ──1:N──→ question_knowledge_mapping
        ──1:N──→ answer_history
        ──1:N──→ mistake_case

mistake_case ──1:N──→ mistake_case_error (→ error_bank)
             ──1:N──→ mistake_case_knowledge (→ knowledge)
             ──1:N──→ teaching_content

knowledge_mastery ──1:N──→ review_plan ──1:N──→ push_record
```

### 核心表说明

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `students` | 学生基本信息 | student_id, name, grade |
| `knowledge` | 知识点定义 | knowledge_id, scope, grade, difficulty |
| `error_bank` | 错因库（三级分类） | error_id, level1/2/3, confidence |
| `question` | 题目库 | question_id, description, answer |
| `answer_history` | 答题历史 | is_correct, judge_result, confidence |
| `mistake_case` | 错题案例 | mistake_case_id, status |
| `knowledge_mastery` | 掌握状态 | master_level, correct/wrong_count |
| `review_plan` | 复习计划 | stage(Day1/3/7), status |
| `push_record` | 推送记录 | push_date, stage, status |
| `teaching_content` | 教学内容 | explanation, hints, practice_list |

### 初始化数据

```python
# knowledge: 12 条核心知识点 + CSV 扩展 255+ 条
# error_bank: 17 条错因标签
# students: 3 名测试学生
# question: 5 道示例题目
# question_knowledge_mapping: 5 条题目-知识点映射
```

---

## 📡 API 接口文档

### 外部接口（API Gateway）

#### POST `/api/v1/submit`
提交作业

**请求体**:
```json
{
  "student_id": "S-0001",          // 学生 ID（必填）
  "question_id": "Q-0001",         // 题目 ID（可选）
  "image": "base64...",            // 图片 Base64（可选）
  "original_question": "题目文本",  // 题目文本（可选）
  "student_write": "学生作答",      // 学生作答（可选）
  "grade": "三年级"                // 年级（默认三年级）
}
```

**响应体（正确答案）**:
```json
{
  "status": "success",
  "data": {
    "judge_result": "correct",
    "step_feedback": "计算正确！",
    "knowledge_id": "G-N-2-005",
    "master_level": 0.5,
    "next_action": "practice"
  }
}
```

**响应体（错误答案 + 教学内容）**:
```json
{
  "status": "success",
  "data": {
    "judge_result": "wrong",
    "error_tags": [
      {
        "error_id": "C-001",
        "level1": "计算",
        "level2": "口算与基本运算",
        "level3": "进位加法中十位漏加进位1",
        "confidence": 0.92
      }
    ],
    "knowledge_explanation": "两位数加两位数进位加法...",
    "explanation": "这道题考查进位加法...",
    "hints": ["个位5+8等于多少？", "个位满十了吗？"],
    "practice_list": [{"question": "18+25=？", "answer": "43"}],
    "teaching_mode": "BASIC",
    "master_level": 0.33,
    "review_plan": {
      "review_stages": ["Day1", "Day3", "Day7"],
      "stage_dates": {"Day1": "2024-01-15", "Day3": "2024-01-17", "Day7": "2024-01-21"}
    }
  }
}
```

#### GET `/api/v1/student/{student_id}/mastery`
查询学生掌握度

**响应**:
```json
{
  "status": "success",
  "data": [
    {
      "knowledge_id": "G-N-2-005",
      "knowledge_scope": "100以内进位加法",
      "mastery_status": "pending",
      "master_level": 0.5,
      "correct_count": 1,
      "wrong_count": 1
    }
  ]
}
```

#### GET `/health`
全服务健康检查

**响应**:
```json
{
  "api_gateway": "healthy",
  "services": {
    "analysis": {"status": "healthy"},
    "error_analysis": {"status": "healthy"},
    "knowledge": {"status": "healthy"},
    "teaching": {"status": "healthy"},
    "state": {"status": "healthy"},
    "knowledge_graph": {"status": "unhealthy"}
  }
}
```

### 内部服务接口

| 服务 | 端点 | 方法 | 说明 |
|------|------|------|------|
| Analysis | `/internal/api/v1/analysis/process` | POST | 处理答题分析 |
| | `/health` | GET | 健康检查 |
| Error Analysis | `/internal/api/v1/error-analysis/analyze` | POST | 错因分析 |
| | `/health` | GET | 健康检查 |
| Knowledge | `/internal/api/v1/knowledge/retrieve` | POST | 知识点检索 |
| | `/health` | GET | 健康检查 |
| Teaching | `/internal/api/v1/teaching/generate` | POST | 生成教学内容 |
| | `/internal/api/v1/teaching/frequency-check` | POST | 频率检查 |
| | `/health` | GET | 健康检查 |
| State | `/internal/api/v1/state/update` | POST | 更新掌握状态 |
| | `/internal/api/v1/state/generate-review` | POST | 生成复习计划 |
| | `/internal/api/v1/state/mastery/{student_id}` | GET | 查询掌握度 |
| | `/health` | GET | 健康检查 |
| Review | `/internal/api/v1/review/scheduler/run` | GET | 执行调度 |
| Scheduler | `/internal/api/v1/review/scheduler/today` | GET | 今日任务 |
| | `/internal/api/v1/review/scheduler/student/{id}` | GET | 学生任务 |
| | `/internal/api/v1/review/scheduler/complete/{id}` | POST | 完成任务 |
| | `/health` | GET | 健康检查 |

---

## ⚙️ 配置说明

### LLM 配置 (`services/.env`)

```env
QIANFAN_API_KEY=your_api_key_here
```

### 环境变量

```python
# llm_client.py
_client = OpenAI(
    api_key=os.getenv("QIANFAN_API_KEY"),
    base_url="https://qianfan.baidubce.com/v2"
)
```

### 启用真实 OCR

```python
# all_in_one.py
USE_REAL_OCR = True  # 需要安装 paddleocr

if USE_REAL_OCR:
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
```

---

## 📊 工作流程详解

### 作业提交流程

```
学生提交作业
     │
     ▼
┌─────────────────────────────────┐
│  1. Analysis Service (8081)    │
│  • OCR 文字识别                 │
│  • 答案判定（正确/错误/抄袭）  │
│  • 步骤分析                     │
└─────────────────────────────────┘
     │
     ├── 正确 → State Service → 更新掌握度
     │
     ├── 抄袭 → 返回引导提示
     │
     └── 错误 ↓
          │
┌─────────────────────────────────┐
│  2. Error Analysis Agent (8082) │
│  • LLM 错因分析                 │
│  • 错误标签匹配                 │
│  • 知识点映射                   │
│  • 置信度校验（<0.7 拒判）      │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  3. Knowledge Service (8083)    │
│  • 获取知识点详情               │
│  • 大纲范围验证                 │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  4. Teaching Service (8084)     │
│  • 频率限制检查                 │
│  • LLM 生成教学内容             │
│  • 三档模式选择                 │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  5. State Service (8085)        │
│  • 更新掌握状态                 │
│  • 生成复习计划                 │
└─────────────────────────────────┘
```

### 复习调度流程

```
Review Scheduler (8086)
     │
     ▼
┌─────────────────────────────────┐
│  每小时执行一次 run_scheduler() │
└─────────────────────────────────┘
     │
     ▼
查询今日待推送任务 (push_record WHERE push_date = today)
     │
     ▼
更新状态为 "pushing"，返回任务列表
     │
     ▼
学生完成复习 → POST complete/{id}
     │
     ├── 答对 → correct_count++
     │         掌握度提高
     │         全部答对 → 完成所有复习计划
     │
     └── 答错 → wrong_count++
              掌握度降低
              连续答错 → 取消复习，教师介入
```

---

## 🛠️ 公共工具模块

### `mastery_utils.py` - 掌握度计算

```python
def calculate_mastery(correct_count: int, wrong_count: int) -> tuple:
    """
    根据连续答对/答错次数计算掌握度
    
    返回: (master_level: float, mastery_status: str)
    """
    if correct_count >= 2:
        return 1.00, "mastered"
    elif wrong_count >= 2:
        return 0.00, "weak"
    elif correct_count == 0 and wrong_count == 0:
        return 0.00, "pending"
    else:
        total = correct_count + wrong_count
        master_level = (correct_count * 0.5) / total
        return round(master_level, 2), "pending"
```

### `id_utils.py` - ID 生成

```python
import uuid

def generate_id(prefix: str) -> str:
    """
    生成全局唯一 ID
    
    格式: {prefix}-{8位十六进制大写}
    示例: MC-A1B2C3D4, KM-E5F6G7H8
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
```

### `llm_client.py` - LLM 调用

```python
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(
    api_key=os.getenv("QIANFAN_API_KEY"),
    base_url="https://qianfan.baidubce.com/v2"
)

def call_llm(system_prompt: str, user_prompt: str, 
             model: str = "ernie-4.5-turbo-32k") -> str:
    """调用百度千帆大模型"""
    completion = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content
```

---

## 📝 请求/响应模型

### SubmitRequest

```python
class SubmitRequest(BaseModel):
    student_id: str                    # 学生 ID
    question_id: Optional[str] = None  # 题目 ID
    image: Optional[str] = None        # 图片 Base64
    original_question: Optional[str] = None  # 题目文本
    student_write: Optional[str] = None      # 学生作答
    grade: Optional[str] = "三年级"   # 年级
```

### ErrorTag

```python
class ErrorTag(BaseModel):
    error_id: str        # 错因 ID (e.g., C-001)
    level1: str          # 一级分类 (e.g., 计算)
    level2: str          # 二级分类 (e.g., 口算与基本运算)
    level3: str          # 三级分类 (e.g., 进位加法中十位漏加进位1)
    confidence: float    # 置信度 (0.0-1.0)
```

### PracticeQuestion

```python
class PracticeQuestion(BaseModel):
    question_id: str
    question_description: str
    difficulty: str
    answer: str
    solution: str
```

---

## 🧪 测试示例

### 正确答案测试

```python
import requests

response = requests.post("http://localhost:8000/api/v1/submit", json={
    "student_id": "S-0001",
    "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
    "student_write": "25+38=63"
})
# → judge_result: correct, master_level: 1.0
```

### 错误答案测试

```python
response = requests.post("http://localhost:8000/api/v1/submit", json={
    "student_id": "S-0001",
    "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
    "student_write": "25+38=53"  # 忘记加进位1
})
# → error_tags: [C-001 进位加法中十位漏加进位1]
# → teaching_mode: BASIC
# → review_plan: Day1/Day3/Day7
```

### 抄袭检测测试

```python
response = requests.post("http://localhost:8000/api/v1/submit", json={
    "student_id": "S-0001",
    "original_question": "小明有25颗糖果，小红有38颗糖果，他们一共有多少颗糖果？",
    "student_write": "63"  # 只有答案，无计算过程
})
# → is_copy: true, next_action: guide
```

### 掌握度查询

```python
response = requests.get("http://localhost:8000/api/v1/student/S-0001/mastery")
# → 返回学生所有知识点掌握状态
```

---

## 🔮 后续规划

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 知识图谱转接层 | 高 | Knowledge Service → Neo4j |
| 真实 OCR 集成 | 高 | PaddleOCR 替换模拟 |
| AI 分析引擎升级 | 高 | 全链路 LLM 集成 |
| 掌握度算法优化 | 中 | 引入 EF 系数、五档分类 |
| 多轮对话教学 | 中 | 支持追问、交互式辅导 |
| 作业批量提交 | 低 | 支持一次多题 |
| 教师管理后台 | 低 | 查看进度、调整策略 |

---

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) | 项目总览与功能清单 |
| [api/endpoints.md](./api/endpoints.md) | API 端点详细文档 |
| [contracts/service_contracts.md](./contracts/service_contracts.md) | 服务间接口契约 |
| [state_machine/state_transition_table.md](./state_machine/state_transition_table.md) | 状态机转换表 |

---

## 📄 License

© 2024 CTDZ Agent Team. All rights reserved.