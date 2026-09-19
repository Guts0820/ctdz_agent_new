"""压测脚本的离线单测：分位数定义、用例构造、日志事件解析与聚合。"""

import json
from datetime import datetime

import pytest

from backend.tools.loadtest import submit_bench as bench


def test_percentile_uses_nearest_rank_without_interpolation() -> None:
    values = list(range(1, 101))

    assert bench.percentile(values, 0.50) == 50
    assert bench.percentile(values, 0.95) == 95
    assert bench.percentile(values, 0.99) == 99
    assert bench.percentile([7.0], 0.99) == 7.0


def test_percentile_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        bench.percentile([], 0.5)
    with pytest.raises(ValueError):
        bench.percentile([1.0], 0.0)


def test_summarize_reports_expected_statistics() -> None:
    summary = bench.summarize([40.0, 10.0, 30.0, 20.0])

    assert summary["count"] == 4
    assert summary["min"] == 10.0
    assert summary["mean"] == 25.0
    assert summary["p50"] == 20.0
    assert summary["p95"] == 40.0
    assert summary["max"] == 40.0


def test_summarize_handles_no_samples() -> None:
    assert bench.summarize([]) == {"count": 0}


def test_make_wrong_answer_changes_the_last_number() -> None:
    assert bench.make_wrong_answer("63") == "64"
    assert bench.make_wrong_answer("25+38=63") == "25+38=64"
    assert bench.make_wrong_answer("63个") == "64个"
    assert bench.make_wrong_answer("没有数字") == "没有数字个"


def test_build_cases_alternates_scenarios_and_keeps_canonical_answer() -> None:
    questions = [{"id": "Q1", "text": "1+1=", "answer": "2", "grade": "一年级"}]

    cases = bench.build_cases(questions, ["S-0001", "S-0002"], 4, "mixed")

    assert [case["scenario"] for case in cases] == ["correct", "wrong", "correct", "wrong"]
    assert [case["student_id"] for case in cases] == ["S-0001", "S-0002", "S-0001", "S-0002"]
    assert cases[0]["payload"]["student_write"] == "2"
    assert cases[1]["payload"]["student_write"] == "3"
    assert cases[0]["payload"]["original_question"] == "1+1="
    assert cases[0]["payload"]["grade"] == "一年级"
    assert cases[0]["expected_judge_result"] == "correct"
    assert cases[1]["expected_judge_result"] == "wrong"


def test_build_cases_reuses_questions_when_total_exceeds_bank_size() -> None:
    questions = [{"id": "Q1", "text": "1+1=", "answer": "2"}]

    cases = bench.build_cases(questions, ["S-0001"], 3, "correct")

    assert [case["question_id"] for case in cases] == ["Q1", "Q1", "Q1"]
    assert all(case["payload"]["student_write"] == "2" for case in cases)


def test_build_cases_skips_questions_without_a_canonical_answer() -> None:
    questions = [
        {"id": "Q1", "text": "缺答案", "answer": ""},
        {"id": "Q2", "text": "有答案", "answer": "5"},
    ]

    cases = bench.build_cases(questions, ["S-0001"], 2, "correct")

    assert {case["question_id"] for case in cases} == {"Q2"}


def test_build_cases_rejects_missing_inputs() -> None:
    with pytest.raises(ValueError):
        bench.build_cases([], ["S-0001"], 1, "correct")
    with pytest.raises(ValueError):
        bench.build_cases([{"id": "Q1", "text": "x", "answer": "1"}], [], 1, "correct")


def test_parse_log_line_reads_structured_events() -> None:
    line = (
        '2026-09-19 10:27:58,400 INFO ctdz_backend '
        '{"event": "submit.stage", "request_id": "bench-00001", "stage": "判题服务", "elapsed_ms": 1200.5, "ok": true}'
    )

    parsed = bench.parse_log_line(line)

    assert parsed is not None
    assert parsed["event"] == "submit.stage"
    assert parsed["request_id"] == "bench-00001"
    assert parsed["stage"] == "判题服务"
    assert parsed["elapsed_ms"] == 1200.5
    assert parsed["timestamp"] == datetime(2026, 9, 19, 10, 27, 58, 400000)


def test_parse_log_line_ignores_access_logs_and_broken_json() -> None:
    assert bench.parse_log_line("INFO:     127.0.0.1:1234 - GET /health HTTP/1.1 200 OK") is None
    assert bench.parse_log_line('2026-09-19 10:27:58,400 INFO ctdz_backend {"event": 乱码') is None
    assert bench.parse_log_line('2026-09-19 10:27:58,400 INFO ctdz_backend ["not", "an", "object"]') is None


def test_collect_events_filters_by_event_name_and_window(tmp_path) -> None:
    (tmp_path / "API_Gateway.log").write_text(
        "\n".join(
            [
                '2026-09-19 10:00:00,000 INFO ctdz_backend {"event": "submit.stage", "stage": "判题服务", "elapsed_ms": 100.0, "ok": true}',
                '2026-09-19 10:05:00,000 INFO ctdz_backend {"event": "model.call", "kind": "llm", "model": "qwen-plus"}',
                '2026-09-19 23:00:00,000 INFO ctdz_backend {"event": "submit.stage", "stage": "知识服务", "elapsed_ms": 900.0, "ok": true}',
            ]
        ),
        encoding="utf-8",
    )

    events = bench.collect_events(
        tmp_path,
        datetime(2026, 9, 19, 9, 59, 0),
        datetime(2026, 9, 19, 10, 10, 0),
        (bench.STAGE_EVENT, bench.MODEL_EVENT),
    )

    assert [event["stage"] for event in events[bench.STAGE_EVENT]] == ["判题服务"]
    assert len(events[bench.MODEL_EVENT]) == 1
    assert events[bench.STAGE_EVENT][0]["source"] == "API_Gateway.log"


def test_summarize_stages_reports_share_and_failures() -> None:
    stage_events = [
        {"stage": "判题服务", "elapsed_ms": 1000.0, "ok": True},
        {"stage": "判题服务", "elapsed_ms": 3000.0, "ok": False},
        {"stage": "教学生成服务", "elapsed_ms": 4000.0, "ok": True},
    ]

    summary = bench.summarize_stages(stage_events)

    assert summary["教学生成服务"]["calls"] == 1
    assert summary["教学生成服务"]["share"] == 0.5
    assert summary["判题服务"]["calls"] == 2
    assert summary["判题服务"]["mean_ms"] == 2000.0
    assert summary["判题服务"]["p95_ms"] == 3000.0
    assert summary["判题服务"]["failed_calls"] == 1


def test_summarize_stages_ignores_events_without_elapsed() -> None:
    assert bench.summarize_stages([{"stage": "判题服务", "elapsed_ms": None}]) == {}


def test_summarize_model_calls_counts_by_kind() -> None:
    events = [
        {"kind": "llm"},
        {"kind": "llm"},
        {"kind": "embedding"},
    ]

    assert bench.summarize_model_calls(events) == {"by_kind": {"llm": 2, "embedding": 1}, "total": 3}


def test_stage_totals_by_request_groups_elapsed_time() -> None:
    stage_events = [
        {"request_id": "r1", "stage": "判题服务", "elapsed_ms": 100.0},
        {"request_id": "r1", "stage": "判题服务", "elapsed_ms": 50.0},
        {"request_id": "r1", "stage": "知识服务", "elapsed_ms": 25.0},
        {"request_id": "r2", "stage": "知识服务", "elapsed_ms": 10.0},
        {"stage": "知识服务", "elapsed_ms": 10.0},
    ]

    totals = bench.stage_totals_by_request(stage_events)

    assert totals["r1"] == {"判题服务": 150.0, "知识服务": 25.0}
    assert totals["r2"] == {"知识服务": 10.0}
    assert set(totals) == {"r1", "r2"}


def test_classify_outcome_maps_status_codes() -> None:
    assert bench.classify_outcome(200, None) == "ok"
    assert bench.classify_outcome(422, None) == "http_4xx"
    assert bench.classify_outcome(429, None) == "http_429"
    assert bench.classify_outcome(503, None) == "http_5xx"
    assert bench.classify_outcome(None, "timeout") == "timeout"
    assert bench.classify_outcome(None, "ConnectError") == "network_error"


def test_build_report_joins_requests_with_log_events(tmp_path) -> None:
    (tmp_path / "API_Gateway.log").write_text(
        "\n".join(
            [
                '2026-09-19 10:00:00,000 INFO ctdz_backend {"event": "submit.stage", "request_id": "bench-00000", "stage": "判题服务", "elapsed_ms": 2000.0, "ok": true}',
                '2026-09-19 10:00:01,000 INFO ctdz_backend {"event": "model.call", "kind": "llm", "request_id": "bench-00000"}',
            ]
        ),
        encoding="utf-8",
    )
    args = bench.parse_args([])
    args.cases = bench.build_cases([{"id": "Q1", "text": "1+1=", "answer": "2"}], ["S-0001"], 2, "mixed")
    results = [
        {
            "index": 0,
            "request_id": "bench-00000",
            "scenario": "correct",
            "student_id": "S-0001",
            "question_id": "Q1",
            "expected_judge_result": "correct",
            "judge_result": "correct",
            "scenario_matched": True,
            "status_code": 200,
            "outcome": "ok",
            "ok": True,
            "latency_ms": 2500.0,
            "timeout_s": 120.0,
            "error": None,
            "detail": "",
        },
        {
            "index": 1,
            "request_id": "bench-00001",
            "scenario": "wrong",
            "student_id": "S-0001",
            "question_id": "Q1",
            "expected_judge_result": "wrong",
            "judge_result": "correct",
            "scenario_matched": False,
            "status_code": 503,
            "outcome": "http_5xx",
            "ok": False,
            "latency_ms": 100.0,
            "timeout_s": 120.0,
            "error": None,
            "detail": "教学生成服务暂不可用",
        },
        {
            "index": 2,
            "request_id": "bench-00002",
            "scenario": "wrong",
            "student_id": "S-0001",
            "question_id": "Q1",
            "expected_judge_result": "wrong",
            "judge_result": "correct",
            "scenario_matched": False,
            "status_code": 200,
            "outcome": "ok",
            "ok": True,
            "latency_ms": 400.0,
            "timeout_s": 120.0,
            "error": None,
            "detail": "",
        },
    ]

    report = bench.build_report(
        args,
        results,
        datetime(2026, 9, 19, 9, 59, 59),
        datetime(2026, 9, 19, 10, 0, 2),
        tmp_path,
        {"api_gateway": "healthy"},
    )

    summary = report["summary"]
    assert summary["requests"] == 3
    assert summary["success"] == 2
    assert summary["success_rate"] == 0.6667
    assert summary["status_counts"] == {"200": 2, "503": 1}
    assert summary["outcome_counts"] == {"ok": 2, "http_5xx": 1}
    assert summary["model_calls"]["total"] == 1
    assert summary["model_calls"]["per_request"] == 0.333
    assert summary["stages"]["判题服务"]["calls"] == 1
    assert summary["stage_coverage"][bench.STAGE_EVENT] == 1
    # 只有真正拿到判题结果的请求才参与场景校验，503 属于失败而不是场景不符
    assert summary["scenario_mismatch"]["count"] == 1
    assert summary["scenario_mismatch"]["examples"][0]["request_id"] == "bench-00002"
    assert report["requests"][0]["stages"] == {"判题服务": 2000.0}
    assert report["requests"][1]["stages"] == {}
    assert report["cases"][1]["student_write"] == "3"
    assert "成功率 66.7%" in bench.format_report({**report, "json_path": "x.json"})
