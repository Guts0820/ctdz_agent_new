import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ExerciseRecord:
    timestamp: datetime
    is_correct: bool
    error_causes: List[str] = None


@dataclass
class KnowledgePoint:
    knowledge_id: str
    title: str
    importance: float = 0.8


@dataclass
class MasteryResult:
    knowledge_id: str
    title: str
    accuracy: float
    consistency: float
    retention: float
    error_control: float
    raw_mastery: float
    confidence: float
    final_mastery: float
    priority: float
    skill_gap: float
    forgetting_risk: float
    trend: float
    state: str


ERROR_SEVERITY = {
    "概念错误": 0.90,
    "方法错误": 0.80,
    "审题错误": 0.45,
    "计算错误": 0.50,
    "粗心大意": 0.30,
    "其他": 0.50,
}

MASTERY_WEIGHTS = {
    "accuracy": 0.4,
    "consistency": 0.25,
    "retention": 0.2,
    "error_control": 0.15,
}

PRIORITY_WEIGHTS = {
    "skill_gap": 0.35,
    "forgetting_risk": 0.25,
    "importance": 0.2,
    "trend": 0.2,
}


def truncate(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(min_val, min(max_val, value))


def calculate_bayesian_smooth_accuracy(total_correct: int, total_wrong: int) -> float:
    alpha_prior = 2
    beta_prior = 2
    return (total_correct + alpha_prior) / (total_correct + total_wrong + alpha_prior + beta_prior) * 100


def calculate_recent_weighted_accuracy(recent_results: List[int], decay_factor: float = 0.75) -> float:
    if not recent_results:
        return 50.0
    
    n = min(len(recent_results), 10)
    recent_results = recent_results[-n:]
    
    weights = [math.pow(decay_factor, i) for i in range(n)][::-1]
    total_weight = sum(weights)
    
    weighted_sum = sum(r * w for r, w in zip(recent_results, weights))
    return (weighted_sum / total_weight) * 100 if total_weight > 0 else 50.0


def calculate_accuracy(total_correct: int, total_wrong: int, recent_results: List[int]) -> float:
    historical_acc = calculate_bayesian_smooth_accuracy(total_correct, total_wrong)
    recent_acc = calculate_recent_weighted_accuracy(recent_results)
    
    if total_correct + total_wrong == 0:
        return 50.0
    
    return truncate(0.3 * historical_acc + 0.7 * recent_acc)


def calculate_volatility(recent_results: List[int]) -> float:
    m = len(recent_results)
    if m < 2:
        return 0.0
    
    changes = 0
    for i in range(1, m):
        if recent_results[i] != recent_results[i-1]:
            changes += 1
    
    return changes / (m - 1)


def count_consecutive(recent_results: List[int], target: int) -> int:
    count = 0
    for r in reversed(recent_results):
        if r == target:
            count += 1
        else:
            break
    return count


def calculate_consistency(recent_results: List[int]) -> float:
    if not recent_results:
        return 50.0
    
    m = min(len(recent_results), 10)
    recent_results = recent_results[-m:]
    
    recent_acc = sum(recent_results) / len(recent_results) * 100
    volatility = calculate_volatility(recent_results)
    consecutive_correct = count_consecutive(recent_results, 1)
    consecutive_wrong = count_consecutive(recent_results, 0)
    
    reward = 3 * consecutive_correct
    penalty = 8 * consecutive_wrong
    
    consistency = recent_acc - 30 * volatility + reward - penalty
    return truncate(consistency)


def calculate_memory_stability_period(accuracy: float, consecutive_correct: int, consecutive_wrong: int) -> float:
    base_period = 7.0
    accuracy_bonus = accuracy / 100 * 7.0
    streak_bonus = consecutive_correct * 2.0
    error_penalty = consecutive_wrong * 3.0
    
    S = base_period + accuracy_bonus + streak_bonus - error_penalty
    return max(1.0, S)


def calculate_retention(days_since_last_correct: float, stability_period: float) -> float:
    if days_since_last_correct <= 0:
        return 100.0
    
    retention = math.exp(-days_since_last_correct / stability_period) * 100
    return truncate(retention)


def calculate_error_severity(error_causes: List[str]) -> float:
    if not error_causes:
        return 0.0
    
    max_severity = 0.0
    for cause in error_causes:
        max_severity = max(max_severity, ERROR_SEVERITY.get(cause, 0.5))
    
    return max_severity * 100


def calculate_recent_error_severity(recent_errors: List[List[str]]) -> float:
    if not recent_errors:
        return 0.0
    
    n = min(len(recent_errors), 5)
    recent_errors = recent_errors[-n:]
    
    decay_factor = 0.7
    weights = [math.pow(decay_factor, i) for i in range(n)][::-1]
    total_weight = sum(weights)
    
    weighted_sum = 0.0
    for errors, weight in zip(recent_errors, weights):
        weighted_sum += calculate_error_severity(errors) * weight
    
    return (weighted_sum / total_weight) if total_weight > 0 else 0.0


def calculate_error_control(recent_errors: List[List[str]], consecutive_wrong: int) -> float:
    if not recent_errors:
        return 100.0
    
    severity = calculate_recent_error_severity(recent_errors)
    error_control = 100 - severity - 5 * consecutive_wrong
    
    return truncate(error_control)


def calculate_confidence(n: int) -> float:
    if n <= 0:
        return 0.0
    return 1.0 - math.exp(-n / 5.0)


def calculate_raw_mastery(accuracy: float, consistency: float, retention: float, error_control: float) -> float:
    return (
        MASTERY_WEIGHTS["accuracy"] * accuracy +
        MASTERY_WEIGHTS["consistency"] * consistency +
        MASTERY_WEIGHTS["retention"] * retention +
        MASTERY_WEIGHTS["error_control"] * error_control
    )


def calculate_final_mastery(raw_mastery: float, confidence: float) -> float:
    return truncate(confidence * raw_mastery + (1 - confidence) * 50)


def calculate_skill_gap(accuracy: float, consistency: float, error_control: float) -> float:
    skill_mastery_without_time = 0.5 * accuracy + 0.3 * consistency + 0.2 * error_control
    return truncate(100 - skill_mastery_without_time)


def calculate_forgetting_risk(retention: float, last_result_is_error: bool, consecutive_wrong: int) -> float:
    risk = 100 - retention
    
    if last_result_is_error:
        risk = 0.85 * risk + 15
        if consecutive_wrong >= 2:
            risk = min(100, risk + 10 * (consecutive_wrong - 1))
    
    return truncate(risk)


def calculate_trend(recent_results: List[int]) -> float:
    n = len(recent_results)
    if n < 4:
        return 50.0
    
    split = n // 2
    old_group = recent_results[:split]
    new_group = recent_results[split:]
    
    old_acc = sum(old_group) / len(old_group) * 100 if old_group else 50.0
    new_acc = sum(new_group) / len(new_group) * 100 if new_group else 50.0
    
    trend = 50 + (old_acc - new_acc)
    return truncate(trend)


def calculate_priority(skill_gap: float, forgetting_risk: float, importance: float, trend: float) -> float:
    priority = (
        PRIORITY_WEIGHTS["skill_gap"] * skill_gap +
        PRIORITY_WEIGHTS["forgetting_risk"] * forgetting_risk +
        PRIORITY_WEIGHTS["importance"] * importance +
        PRIORITY_WEIGHTS["trend"] * trend
    )
    return truncate(priority)


def calculate_knowledge_mastery(
    knowledge_id: str,
    title: str,
    exercise_records: List[ExerciseRecord],
    importance: float = 0.8
) -> MasteryResult:
    
    exercise_records.sort(key=lambda x: x.timestamp)
    
    total_correct = sum(1 for r in exercise_records if r.is_correct)
    total_wrong = len(exercise_records) - total_correct
    n = len(exercise_records)
    
    recent_results = [1 if r.is_correct else 0 for r in exercise_records]
    recent_errors = [r.error_causes or [] for r in exercise_records if not r.is_correct]
    
    last_correct_time = None
    for record in reversed(exercise_records):
        if record.is_correct:
            last_correct_time = record.timestamp
            break
    
    now = datetime.now()
    if last_correct_time:
        days_since_last_correct = (now - last_correct_time).total_seconds() / (24 * 3600)
    else:
        days_since_last_correct = float('inf')
    
    accuracy = calculate_accuracy(total_correct, total_wrong, recent_results)
    
    consistency = calculate_consistency(recent_results)
    
    consecutive_correct = count_consecutive(recent_results, 1)
    consecutive_wrong = count_consecutive(recent_results, 0)
    
    stability_period = calculate_memory_stability_period(accuracy, consecutive_correct, consecutive_wrong)
    
    if total_correct == 0:
        retention = 0.0
    else:
        retention = calculate_retention(days_since_last_correct, stability_period)
    
    error_control = calculate_error_control(recent_errors, consecutive_wrong)
    
    raw_mastery = calculate_raw_mastery(accuracy, consistency, retention, error_control)
    
    confidence = calculate_confidence(n)
    
    final_mastery = calculate_final_mastery(raw_mastery, confidence)
    
    skill_gap = calculate_skill_gap(accuracy, consistency, error_control)
    
    last_result_is_error = False
    if exercise_records:
        last_result_is_error = not exercise_records[-1].is_correct
    
    forgetting_risk = calculate_forgetting_risk(retention, last_result_is_error, consecutive_wrong)
    
    trend = calculate_trend(recent_results)
    
    priority = calculate_priority(skill_gap, forgetting_risk, importance * 100, trend)
    
    state = "unassessed" if n == 0 else "assessed"
    
    return MasteryResult(
        knowledge_id=knowledge_id,
        title=title,
        accuracy=accuracy,
        consistency=consistency,
        retention=retention,
        error_control=error_control,
        raw_mastery=raw_mastery,
        confidence=confidence,
        final_mastery=final_mastery,
        priority=priority,
        skill_gap=skill_gap,
        forgetting_risk=forgetting_risk,
        trend=trend,
        state=state
    )


def calculate_five_dimension_scores(mastery_results: List[MasteryResult]) -> List[Dict]:
    dimension_keywords = {
        "operation": ["运算", "乘法", "除法", "加法", "减法", "计算", "口算", "笔算"],
        "logic": ["推理", "逻辑", "判断", "分析", "证明", "归纳", "演绎", "规律"],
        "spatial": ["空间", "图形", "几何", "观察", "位置", "方向", "对称", "面积", "体积"],
        "language": ["应用题", "文字题", "阅读", "理解", "表达", "描述", "解释"],
        "resilience": []
    }
    
    dimension_scores = {}
    
    for dim, keywords in dimension_keywords.items():
        related = []
        for result in mastery_results:
            if not keywords:
                related.append(result)
            else:
                for kw in keywords:
                    if kw in result.title:
                        related.append(result)
                        break
        
        if related:
            avg_mastery = sum(r.final_mastery for r in related) / len(related)
            avg_confidence = sum(r.confidence for r in related) / len(related)
            final_score = truncate(avg_confidence * avg_mastery + (1 - avg_confidence) * 50)
        else:
            final_score = 50.0
        
        dimension_scores[dim] = final_score
    
    dimension_labels = {
        "operation": "运算能力",
        "logic": "逻辑思维",
        "spatial": "空间想象",
        "language": "语言推理",
        "resilience": "学习韧性"
    }
    
    for dim in dimension_scores:
        if dim == "resilience":
            high_priority = [r for r in mastery_results if r.priority > 70]
            if high_priority:
                resilience_score = 100 - sum(r.priority for r in high_priority) / len(high_priority)
            else:
                resilience_score = 80.0
            dimension_scores[dim] = truncate(resilience_score)
    
    return [
        {
            "dimension": dim,
            "score": round(dimension_scores[dim], 1),
            "max_score": 100,
            "label": dimension_labels[dim]
        }
        for dim in dimension_keywords
    ]


def calculate_class_average_mastery(
    student_mastery_results: List[List[MasteryResult]]
) -> List[Dict]:
    knowledge_map = {}
    
    for student_results in student_mastery_results:
        for result in student_results:
            if result.knowledge_id not in knowledge_map:
                knowledge_map[result.knowledge_id] = {
                    "title": result.title,
                    "masteries": [],
                    "count": 0
                }
            knowledge_map[result.knowledge_id]["masteries"].append(result.final_mastery)
            knowledge_map[result.knowledge_id]["count"] += 1
    
    average_results = []
    for knowledge_id, data in knowledge_map.items():
        avg_mastery = sum(data["masteries"]) / len(data["masteries"]) if data["masteries"] else 0
        average_results.append({
            "knowledge_id": knowledge_id,
            "title": data["title"],
            "average_mastery": round(avg_mastery, 1),
            "student_count": data["count"]
        })
    
    return sorted(average_results, key=lambda x: x["average_mastery"])