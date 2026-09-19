"""提交链路并发压测脚本（Phase 0 基线测量）。

用法::

    python backend/tools/loadtest/submit_bench.py --concurrency 45 --total 200 --scenario mixed

脚本做三件事：

1. 从网关 ``GET /api/questions`` 取真实题库，按 ``--scenario`` 造出正确/错误作答；
2. 用 ``asyncio`` + ``httpx`` 打 ``/api/v1/submit``，记录客户端延迟、状态码与判题结果；
3. 从 ``backend/logs/*.log`` 里聚合 ``submit.stage``（网关各下游阶段耗时）与
   ``model.call``（Qwen LLM / Embedding 调用次数）事件，输出一张表并把原始数据写入
   ``backend/logs/bench-<timestamp>.json``。

所有数字都来自真实请求，脚本不估算、不补全缺失的阶段数据 —— 如果日志里没有
``submit.stage`` 事件（例如埋点未生效），阶段一节会显式说明"未检测到"。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_LOG_DIR = PROJECT_ROOT / "backend" / "logs"
DEFAULT_JSON_DIR = PROJECT_ROOT / "backend" / "logs"
SUBMIT_PATH = "/api/v1/submit"
QUESTION_LIST_PATH = "/api/questions"
STAGE_EVENT = "submit.stage"
MODEL_EVENT = "model.call"
LOG_TS_FORMAT = "%Y-%m-%d %H:%M:%S,%f"
LOG_LINE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s.*?(?P<payload>\{.*\})\s*$")


# --------------------------------------------------------------------------- #
# 统计与数据构造（纯函数，便于离线单测）
# --------------------------------------------------------------------------- #

def percentile(values: Sequence[float], quantile: float) -> float:
    """最近秩法（nearest-rank）分位数，不做插值。

    n 个样本时 Pq 取升序第 ``ceil(q * n)`` 个样本；这是压测报告里最保守、
    最容易复算的定义（n=200 时 P95 就是第 190 个样本，可以直接去 JSON 里核对）。
    """
    if not values:
        raise ValueError("percentile() 需要至少一个样本")
    if not 0 < quantile <= 1:
        raise ValueError("quantile 必须落在 (0, 1] 区间")
    ordered = sorted(values)
    rank = math.ceil(quantile * len(ordered))
    return float(ordered[min(max(rank - 1, 0), len(ordered) - 1)])


def summarize(values: Sequence[float]) -> dict[str, float | int]:
    """延迟样本的整体统计量（毫秒）。"""
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": round(float(ordered[0]), 2),
        "mean": round(sum(ordered) / len(ordered), 2),
        "p50": round(percentile(ordered, 0.50), 2),
        "p95": round(percentile(ordered, 0.95), 2),
        "p99": round(percentile(ordered, 0.99), 2),
        "max": round(float(ordered[-1]), 2),
    }


def make_wrong_answer(answer: str) -> str:
    """把标准答案的最后一个数字改掉，得到一道"看起来像学生写的"错误作答。"""
    matches = list(re.finditer(r"\d+", answer))
    if not matches:
        return f"{answer}个"
    last = matches[-1]
    value = int(last.group())
    replacement = str((value + 1) % (10 ** len(last.group())))
    return f"{answer[:last.start()]}{replacement}{answer[last.end():]}"


def build_cases(
    questions: Sequence[dict[str, Any]],
    students: Sequence[str],
    total: int,
    scenario: str,
) -> list[dict[str, Any]]:
    """按题库与学生名单生成 total 个提交用例（题库不足时循环复用）。"""
    usable = [q for q in questions if str(q.get("id") or "").strip() and str(q.get("answer") or "").strip()]
    if not usable:
        raise ValueError("题库里没有同时具备 id 与 answer 的题目，先导入 canonical 题目再压测")
    if not students:
        raise ValueError("学生名单为空")
    cases = []
    for index in range(total):
        question = usable[index % len(usable)]
        student_id = students[index % len(students)]
        correct = str(question["answer"]).strip()
        case_scenario = scenario if scenario in {"correct", "wrong"} else ("correct" if index % 2 == 0 else "wrong")
        student_write = correct if case_scenario == "correct" else make_wrong_answer(correct)
        payload = {
            "student_id": student_id,
            "question_id": str(question["id"]),
            "original_question": str(question.get("text") or "").strip(),
            "student_write": student_write,
        }
        grade = str(question.get("grade") or "").strip()
        if grade:
            payload["grade"] = grade
        cases.append(
            {
                "index": index,
                "scenario": case_scenario,
                "expected_judge_result": "correct" if case_scenario == "correct" else "wrong",
                "question_id": str(question["id"]),
                "student_id": student_id,
                "standard_answer": correct,
                "payload": payload,
            }
        )
    return cases


def parse_log_line(line: str) -> dict[str, Any] | None:
    """解析一条带 JSON 尾巴的服务日志；非结构化行返回 None。"""
    match = LOG_LINE_RE.match(line.rstrip("\n"))
    if not match:
        return None
    try:
        payload = json.loads(match.group("payload"))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        payload["timestamp"] = datetime.strptime(match.group("ts"), LOG_TS_FORMAT)
    except ValueError:
        return None
    return payload


def collect_events(
    log_dir: Path,
    window_start: datetime,
    window_end: datetime,
    events: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """按事件名收集时间窗口内的结构化日志事件。"""
    wanted = set(events)
    collected: dict[str, list[dict[str, Any]]] = {name: [] for name in wanted}
    if not log_dir.exists():
        return collected
    for path in sorted(log_dir.glob("*.log")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            parsed = parse_log_line(line)
            if parsed is None or parsed.get("event") not in wanted:
                continue
            timestamp = parsed["timestamp"]
            if not window_start <= timestamp <= window_end:
                continue
            parsed["source"] = path.name
            collected[parsed["event"]].append(parsed)
    return collected


def summarize_stages(stage_events: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按 stage 聚合耗时：次数、总量、P50/P95 与占全部下游耗时的比例。"""
    buckets: dict[str, list[float]] = {}
    for event in stage_events:
        stage = str(event.get("stage") or "unknown")
        try:
            elapsed = float(event.get("elapsed_ms"))
        except (TypeError, ValueError):
            continue
        buckets.setdefault(stage, []).append(elapsed)
    total_ms = sum(sum(values) for values in buckets.values())
    summary: dict[str, dict[str, Any]] = {}
    for stage, values in sorted(buckets.items(), key=lambda item: -sum(item[1])):
        stage_total = sum(values)
        summary[stage] = {
            "calls": len(values),
            "total_ms": round(stage_total, 2),
            "mean_ms": round(stage_total / len(values), 2),
            "p50_ms": round(percentile(values, 0.50), 2),
            "p95_ms": round(percentile(values, 0.95), 2),
            "share": round(stage_total / total_ms, 4) if total_ms else 0.0,
            "failed_calls": sum(1 for event in stage_events if str(event.get("stage")) == stage and not event.get("ok", True)),
        }
    return summary


def summarize_model_calls(model_events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """按类型统计模型调用次数。"""
    by_kind: dict[str, int] = {}
    for event in model_events:
        kind = str(event.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {"by_kind": by_kind, "total": sum(by_kind.values())}


def stage_totals_by_request(stage_events: Sequence[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """按 request_id 汇总各阶段耗时，用于定位单个慢请求的瓶颈。"""
    totals: dict[str, dict[str, float]] = {}
    for event in stage_events:
        request_id = event.get("request_id")
        if not request_id:
            continue
        try:
            elapsed = float(event.get("elapsed_ms"))
        except (TypeError, ValueError):
            continue
        bucket = totals.setdefault(str(request_id), {})
        stage = str(event.get("stage") or "unknown")
        bucket[stage] = round(bucket.get(stage, 0.0) + elapsed, 2)
    return totals


def classify_outcome(status_code: int | None, error: str | None) -> str:
    if status_code is None:
        return "timeout" if error == "timeout" else "network_error"
    if 200 <= status_code < 300:
        return "ok"
    if status_code == 429:
        return "http_429"
    if status_code >= 500:
        return "http_5xx"
    return "http_4xx"


def load_student_ids(database_path: str | None = None) -> list[str]:
    """默认学生名单取自 SQLite 种子数据；读不到时退回 S-0001。"""
    if database_path is None:
        from backend.shared.config import DATABASE_PATH

        database_path = DATABASE_PATH
    try:
        with sqlite3.connect(database_path) as connection:
            rows = connection.execute("SELECT student_id FROM students ORDER BY student_id").fetchall()
    except sqlite3.Error:
        return ["S-0001"]
    return [str(row[0]) for row in rows] or ["S-0001"]


# --------------------------------------------------------------------------- #
# 压测执行
# --------------------------------------------------------------------------- #

async def submit_once(client: Any, case: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """提交一次作业并记录客户端视角的延迟与结果。"""
    import httpx

    request_id = f"bench-{case['index']:05d}"
    started = time.perf_counter()
    status_code: int | None = None
    error: str | None = None
    judge_result: str | None = None
    detail = ""
    try:
        response = await client.post(
            SUBMIT_PATH,
            json=case["payload"],
            headers={"X-Request-Id": request_id},
        )
        status_code = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            data = body.get("data")
            if isinstance(data, dict):
                judge_result = data.get("judge_result")
            if response.status_code >= 400:
                detail = str(body.get("detail") or body)[:200]
        elif response.status_code >= 400:
            detail = response.text[:200]
    except httpx.TimeoutException:
        error = "timeout"
    except httpx.HTTPError as exc:
        error = type(exc).__name__
        detail = str(exc)[:200]
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    outcome = classify_outcome(status_code, error)
    expected = case["expected_judge_result"]
    return {
        "index": case["index"],
        "request_id": request_id,
        "scenario": case["scenario"],
        "student_id": case["student_id"],
        "question_id": case["question_id"],
        "expected_judge_result": expected,
        "judge_result": judge_result,
        "scenario_matched": judge_result == expected,
        "status_code": status_code,
        "outcome": outcome,
        "ok": outcome == "ok",
        "latency_ms": latency_ms,
        "timeout_s": timeout_s,
        "error": error,
        "detail": detail,
    }


async def run_benchmark(
    base_url: str,
    cases: Sequence[dict[str, Any]],
    concurrency: int,
    timeout_s: float,
    progress_every: int = 0,
) -> list[dict[str, Any]]:
    """按并发度打完所有用例，返回每次请求的记录。"""
    import httpx

    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency + 5)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    for case in cases:
        queue.put_nowait(case)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    step = progress_every or max(1, len(cases) // 20)

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_s),
        limits=limits,
        trust_env=False,
    ) as client:

        async def worker() -> None:
            while True:
                try:
                    case = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                results.append(await submit_once(client, case, timeout_s))
                if len(results) % step == 0:
                    done = len(results)
                    elapsed = time.perf_counter() - started
                    running = summarize([item["latency_ms"] for item in results])
                    print(
                        f"  [{done}/{len(cases)}] 已用 {elapsed:.1f}s | "
                        f"当前 P50 {running['p50'] / 1000:.2f}s P95 {running['p95'] / 1000:.2f}s",
                        flush=True,
                    )

        await asyncio.gather(*[worker() for _ in range(max(1, min(concurrency, len(cases))))])
    results.sort(key=lambda item: item["index"])
    return results


def fetch_check(base_url: str, timeout_s: float = 10.0) -> dict[str, Any]:
    """确认网关卡在跑；顺带报告下游服务健康状态。"""
    import httpx

    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(timeout_s), trust_env=False) as client:
        response = client.get("/health")
        response.raise_for_status()
        return response.json()


def fetch_questions(base_url: str, page_size: int = 100) -> list[dict[str, Any]]:
    """从网关取真实题库（id / text / answer / grade）。"""
    import httpx

    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(30.0), trust_env=False) as client:
        response = client.get(QUESTION_LIST_PATH, params={"page_size": page_size})
        response.raise_for_status()
        body = response.json()
    questions = body.get("data")
    if not isinstance(questions, list):
        raise RuntimeError(f"{QUESTION_LIST_PATH} 返回结构异常：{str(body)[:200]}")
    return [item for item in questions if isinstance(item, dict)]


def count_rate_limit_lines(
    log_dir: Path,
    window_start: datetime,
    window_end: datetime,
    needles: Sequence[str] = (
        "Error code: 429",
        "Throttling",
        "rate limit",
        '"status_code": 429',
    ),
) -> int:
    """统计窗口内提到限流的日志行数（含上游模型限流）。

    只匹配明确的限流措辞，避免把 ``elapsed_ms": 429.0`` 这类数字误记成 429。
    """
    matched = 0
    if not log_dir.exists():
        return 0
    for path in sorted(log_dir.glob("*.log")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            parsed = parse_log_line(line)
            timestamp = parsed["timestamp"] if parsed else None
            if timestamp is not None and not window_start <= timestamp <= window_end:
                continue
            if timestamp is None:
                continue
            if any(needle in line for needle in needles):
                matched += 1
    return matched


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #

def build_report(
    args: argparse.Namespace,
    results: Sequence[dict[str, Any]],
    started_at: datetime,
    finished_at: datetime,
    log_dir: Path,
    health: dict[str, Any] | None,
) -> dict[str, Any]:
    """把请求记录与日志事件合成最终报告。"""
    window_start = started_at - timedelta(seconds=2)
    window_end = finished_at + timedelta(seconds=5)
    events = collect_events(log_dir, window_start, window_end, (STAGE_EVENT, MODEL_EVENT))
    stage_events = events[STAGE_EVENT]
    stage_summary = summarize_stages(stage_events)
    per_request_stages = stage_totals_by_request(stage_events)

    latencies = [item["latency_ms"] for item in results]
    status_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    for item in results:
        status_counts[str(item["status_code"])] = status_counts.get(str(item["status_code"]), 0) + 1
        outcome_counts[item["outcome"]] = outcome_counts.get(item["outcome"], 0) + 1

    duration_s = max((finished_at - started_at).total_seconds(), 1e-6)
    successes = outcome_counts.get("ok", 0)
    mismatches = [item for item in results if item["ok"] and not item["scenario_matched"]]
    model_summary = summarize_model_calls(events[MODEL_EVENT])
    request_scoped_models = sum(1 for event in events[MODEL_EVENT] if event.get("request_id"))

    request_records = []
    for item in results:
        record = dict(item)
        record["stages"] = per_request_stages.get(item["request_id"], {})
        request_records.append(record)

    slowest = sorted(
        (item for item in request_records if item["stages"]),
        key=lambda item: -item["latency_ms"],
    )[:3]

    return {
        "label": args.label,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_s": round(duration_s, 2),
        "config": {
            "base_url": args.base_url,
            "concurrency": args.concurrency,
            "total": len(results),
            "scenario": args.scenario,
            "timeout_s": args.timeout,
            "log_dir": str(log_dir),
        },
        "health": health,
        "summary": {
            "requests": len(results),
            "success": successes,
            "success_rate": round(successes / len(results), 4) if results else 0.0,
            "throughput_rps": round(len(results) / duration_s, 3),
            "latency_ms": summarize(latencies),
            "status_counts": status_counts,
            "outcome_counts": outcome_counts,
            "scenario_mismatch": {
                "count": len(mismatches),
                "examples": [
                    {
                        "request_id": item["request_id"],
                        "scenario": item["scenario"],
                        "expected": item["expected_judge_result"],
                        "judge_result": item["judge_result"],
                    }
                    for item in mismatches[:5]
                ],
            },
            "model_calls": {
                **model_summary,
                "per_request": round(model_summary["total"] / len(results), 3) if results else 0.0,
                "events_with_request_id": request_scoped_models,
            },
            "rate_limit_lines": count_rate_limit_lines(log_dir, window_start, window_end),
            "stages": stage_summary,
            "stage_coverage": {
                STAGE_EVENT: len(stage_events),
                MODEL_EVENT: len(events[MODEL_EVENT]),
                "window": [window_start.isoformat(timespec="seconds"), window_end.isoformat(timespec="seconds")],
            },
            "slowest_requests": [
                {
                    "request_id": item["request_id"],
                    "latency_ms": item["latency_ms"],
                    "status_code": item["status_code"],
                    "stages": item["stages"],
                }
                for item in slowest
            ],
        },
        "cases": [
            {
                "index": item["index"],
                "scenario": item["scenario"],
                "student_id": item["student_id"],
                "question_id": item["question_id"],
                "student_write": next(
                    (case["payload"]["student_write"] for case in args.cases if case["index"] == item["index"]),
                    "",
                ),
            }
            for item in results
        ],
        "requests": request_records,
    }


def format_report(report: dict[str, Any]) -> str:
    """把报告渲染成终端表格。"""
    summary = report["summary"]
    latency = summary["latency_ms"]
    lines = [
        "",
        "=" * 72,
        f"提交链路压测 {report['label'] or ''}".rstrip(),
        "=" * 72,
        f"并发 {report['config']['concurrency']} | 提交 {summary['requests']} 次 | "
        f"成功率 {summary['success_rate'] * 100:.1f}% | 场景 {report['config']['scenario']}",
        f"P50 {latency.get('p50', 0) / 1000:.2f}s | P95 {latency.get('p95', 0) / 1000:.2f}s | "
        f"P99 {latency.get('p99', 0) / 1000:.2f}s | 吞吐 {summary['throughput_rps']:.2f} req/s | "
        f"耗时 {report['duration_s']:.1f}s",
        f"状态码分布 {summary['status_counts']} | 结果分类 {summary['outcome_counts']}",
    ]
    stages = summary.get("stages") or {}
    if stages:
        share_text = " | ".join(
            f"{stage} {data['share'] * 100:.0f}%({data['p50_ms']:.0f}ms/中位)" for stage, data in stages.items()
        )
        lines.append(f"阶段占比：{share_text}")
    else:
        lines.append(f"阶段占比：未检测到 {STAGE_EVENT} 事件（检查网关埋点或 {report['config']['log_dir']} 日志）")

    model_calls = summary["model_calls"]
    kinds = " / ".join(f"{kind} {count}" for kind, count in sorted(model_calls["by_kind"].items()))
    lines.append(
        f"模型调用 {model_calls['total']} 次（{kinds or '无'}，平均 {model_calls['per_request']} 次/提交）| "
        f"客户端 429 {summary['outcome_counts'].get('http_429', 0)} 次 | 日志限流行 {summary['rate_limit_lines']} 条"
    )
    mismatch = summary["scenario_mismatch"]["count"]
    if mismatch:
        lines.append(f"⚠ 场景校验不一致 {mismatch} 次（期望判对/判错与实际不符，见 JSON 的 scenario_mismatch）")
    slowest = summary.get("slowest_requests") or []
    for item in slowest[:1]:
        stage_text = " | ".join(
            f"{stage} {elapsed:.0f}ms" for stage, elapsed in sorted(item["stages"].items(), key=lambda pair: -pair[1])
        )
        lines.append(f"最慢请求 {item['request_id']}：{item['latency_ms'] / 1000:.2f}s → {stage_text}")
    lines.append(f"原始数据：{report['json_path']}")
    lines.append("=" * 72)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="提交链路并发压测（Phase 0 基线）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="网关地址")
    parser.add_argument("--concurrency", type=int, default=10, help="并发提交数")
    parser.add_argument("--total", type=int, default=20, help="总提交次数")
    parser.add_argument("--scenario", choices=["correct", "wrong", "mixed"], default="mixed")
    parser.add_argument("--timeout", type=float, default=120.0, help="单请求客户端超时（秒）")
    parser.add_argument("--students", default="", help="逗号分隔的学生 ID；默认取 SQLite 种子学生")
    parser.add_argument("--page-size", type=int, default=100, help="取题库的条数")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="服务日志目录")
    parser.add_argument("--out", default="", help="报告输出路径；默认 backend/logs/bench-<timestamp>.json")
    parser.add_argument("--label", default="", help="报告标签（如 before-redis / after-redis）")
    parser.add_argument("--cases-in", default="", help="复用之前的用例文件，保证前后对比用同一批输入")
    parser.add_argument("--cases-out", default="", help="把本次用例写入文件，供后续对比复用")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    log_dir = Path(args.log_dir)
    try:
        health = fetch_check(args.base_url)
    except Exception as error:  # noqa: BLE001 - 启动前自检，任何失败都要给出明确提示
        print(f"网关不可用（{args.base_url}）：{error}", file=sys.stderr)
        print("先执行 `python backend/start_all.py` 拉起全栈再压测。", file=sys.stderr)
        return 2

    unhealthy = [
        name
        for name, payload in (health.get("services") or {}).items()
        if isinstance(payload, dict) and payload.get("status") not in {"healthy", "ok"}
    ]
    if unhealthy:
        print(f"⚠ 以下下游服务报告不健康，压测数字会包含它们的失败：{', '.join(unhealthy)}", file=sys.stderr)

    if args.cases_in:
        cases = json.loads(Path(args.cases_in).read_text(encoding="utf-8"))
        print(f"复用用例文件 {args.cases_in}（{len(cases)} 条）", flush=True)
    else:
        try:
            questions = fetch_questions(args.base_url, args.page_size)
        except Exception as error:  # noqa: BLE001
            print(f"取题库失败：{error}", file=sys.stderr)
            return 2
        students = [item.strip() for item in args.students.split(",") if item.strip()] or load_student_ids()
        try:
            cases = build_cases(questions, students, args.total, args.scenario)
        except ValueError as error:
            print(f"构造压测用例失败：{error}", file=sys.stderr)
            return 2
        print(f"题库 {len(questions)} 题，学生 {len(students)} 人，生成 {len(cases)} 条用例", flush=True)

    if args.cases_out:
        Path(args.cases_out).write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"用例已写入 {args.cases_out}", flush=True)

    args.cases = cases
    print(
        f"开始压测：并发 {args.concurrency}，共 {len(cases)} 次提交，场景 {args.scenario}，超时 {args.timeout:.0f}s",
        flush=True,
    )
    started_at = datetime.now()
    results = asyncio.run(run_benchmark(args.base_url, cases, args.concurrency, args.timeout))
    finished_at = datetime.now()

    report = build_report(args, results, started_at, finished_at, log_dir, health)
    timestamp = finished_at.strftime("%Y%m%dT%H%M%S")
    label = f"{args.label}-" if args.label else ""
    out_path = Path(args.out) if args.out else DEFAULT_JSON_DIR / f"bench-{label}{timestamp}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report["json_path"] = str(out_path)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(format_report(report))
    return 0 if report["summary"]["success_rate"] >= 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
