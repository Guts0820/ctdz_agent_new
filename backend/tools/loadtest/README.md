# 提交链路压测（Phase 0 测量 harness）

## 怎么跑

```bash
# 全栈先起来
python backend/start_all.py

# 课堂并发场景（45 人同时交作业）
python backend/tools/loadtest/submit_bench.py --concurrency 45 --total 200 --scenario mixed \
    --label before --timeout 180 \
    --cases-out backend/tools/loadtest/baselines/cases-mixed.json

# 优化后用同一批用例复测（保证输入一致，前后可比）
python backend/tools/loadtest/submit_bench.py --cases-in backend/tools/loadtest/baselines/cases-mixed.json \
    --concurrency 45 --label after-redis
```

| 参数 | 说明 |
| --- | --- |
| `--concurrency` / `--total` | 并发数与总提交次数 |
| `--scenario` | `correct`（照标准答案作答）/ `wrong`（末位数字变更）/ `mixed`（交替） |
| `--cases-in` / `--cases-out` | 复用/导出用例，保证前后对比输入完全一致 |
| `--label` | 报告文件名标签，如 `before` / `after-redis` |
| `--out` | 报告 JSON 输出路径（默认 `backend/logs/bench-<label>-<时间戳>.json`） |

## 脚本测的是什么（每项都有明确定义，面试可复算）

- **延迟分位**：客户端视角（`httpx` 发出到响应返回），**最近秩法**不插值 —— n 个样本的 P95 = 升序第 `ceil(0.95n)` 个样本，n=200 时就是第 190 个样本，可直接在报告 JSON 的 `requests[].latency_ms` 里排序核对。
- **阶段耗时**：网关 `execute_downstream` 每调一次下游就打一条 `submit.stage` 事件；压测给每个请求带 `X-Request-Id`，网关把该 id 放进 `contextvars`，所以**阶段事件能精确归因到具体请求**（`requests[].stages` + `summary.slowest_requests`）。
- **模型调用次数**：`backend/shared/llm_client.call_llm`、`analysis_service/llm_judge`（判题/未收录题判题/重排）、`knowledge_graph_service/embedding.embed_texts` 在**发出请求前**打 `model.call`，统计的是"调用尝试次数"（403/429 也算，因为配额与限流就是要看的对象）。服务进程不接收 `request_id`（Task 4.1 才做透传），所以模型次数按压测时间窗聚合，不能逐请求拆分。
- **限流**：客户端 429 计数 + 日志中明确的限流措辞行数（`Error code: 429` / `Throttling` / `rate limit`），不把 `elapsed_ms: 429.0` 这类数字误算进去。
- **场景校验**：脚本期望"正确作答→判对、错误作答→判错"，不一致会显式报 `⚠ 场景校验不一致 N 次`，避免拿一批实际判错的样本当"优化前基线"。

## 已测基线：2026-09-19（降级模式，**不是**可用于宣称优化效果的基线）

命令：`--concurrency 45 --total 200 --scenario mixed --label fallback-pre`
原始数据：[`baselines/baseline-fallback-pre.json`](baselines/baseline-fallback-pre.json)（200 条请求记录 + 阶段归因）

```
并发 45 | 提交 200 次 | 成功率 50.0%
P50 0.77s | P95 3.47s | P99 4.41s | 吞吐 25.40 req/s | 耗时 7.9s
状态码分布 {'200': 100, '422': 100}
阶段占比：知识服务 43%(2074ms/中位) | 判题服务 40%(288ms/中位) | 错因分析服务 17%(369ms/中位)
模型调用 300 次（全部 403）| 客户端 429 0 次
```

### ⚠ 为什么这张表不能当"优化前基线"

1. **Qwen 调用全部 403，整条链路跑在降级分支上。**
   实测：`POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` →
   403 `AllocationQuota.FreeTierOnly`（免费额度耗尽，需充值或在控制台关闭"仅用免费额度"）。
   因此判题走规则兜底、错因分析拿不到知识点、教学走模板，**延迟不含真实 LLM 耗时**，
   现在测出的 P95 与"优化后"没有可比性。
2. **错答链路当前无法走完：100 次错答全部 422**（实测分布：50 次 `知识服务拒绝请求：… out of syllabus`、
   50 次 `错因分析未能确定知识点，无法继续生成教学内容`）。
   - 根因是题库数据：知识图谱里只有 4 道 `teacher_upload` 题目（`0.8×0.02=` 这类小数乘法），
     `knowledge_id` 为空、与 `KnowledgePoint` 无 `EXAMINES` 关系；
     种子题 `Q-0001..Q-0006`（三年级加减法/周长）在 SQLite 里但**不在图谱中**，直接提交会被判 `422 题目不在题库中`。
   - 于是：错误作答→错因分析无法定位知识点而 422（链路在第 3 段就断了）；
     正确作答→判题通过后因拿不到知识点而短路返回，响应带
     `warning: 无法确定题目对应的知识点，跳过状态更新`、`next_action=guide`、无 `mastery`。
     **7 段串行链路的中间 4 段（知识/频控/状态/教学）根本没被执行到。**
3. 因此这 200 次里 100 次 200 全是"判对后短路"，100 次 422 全是失败，
   **没有任何一次请求走完过完整的错答链路** —— 这也是 Phase 4「错答链路 P95」暂时没有测量对象的原因。

### 解除阻塞需要的外部动作（按优先级）

| # | 动作 | 谁做 | 影响 |
| --- | --- | --- | --- |
| 1 | 给 Qwen 账号充值或在控制台关闭"仅用免费额度"（或换一个可用 key 写入 `backend/.env`） | 用户 | 让 LLM 链路真实可测；否则 Phase 2/3/4 的所有数字都是降级分支的数字 |
| 2 | 让题库里有"带知识点映射的 canonical 题"（走教师录题/标准答案上传流程，或把 `Q-0001..Q-0006` 导入图谱并绑定 `knowledge_id`） | 用户/后续 Task | 错答链路能走完，Phase 4 的"错答链路 P95"才有对象 |
| 3 | （可选）把 `request_id` 透传到下游服务 | Task 4.1 | 模型调用次数可逐请求拆分，缓存命中率可对齐到请求 |

> 纪律：**在这三项解决之前，不要在任何文档或简历里写"延迟下降 X%"**。
