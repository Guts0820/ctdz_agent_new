"""SQLite-backed growth-report and ability-radar aggregation."""

import json
import sqlite3
from datetime import datetime, timedelta

from backend.shared.config import DATABASE_PATH
from backend.shared.observability import log_event
from .ability_mapping import ABILITY_DIMENSIONS, MAPPING_VERSION
from .learning_path import LearningPathRecommender, normalize_student_id


class GrowthReportContractService:
    """Build a read-only growth report from persisted learning facts."""

    def __init__(self, path_recommender: LearningPathRecommender | None = None) -> None:
        self.path_recommender = path_recommender or LearningPathRecommender()

    def generate_contract_report(self, student_id: str | int) -> dict:
        normalized_student_id = normalize_student_id(student_id)
        degradation_reasons: list[str] = []
        try:
            with sqlite3.connect(DATABASE_PATH) as connection:
                connection.row_factory = sqlite3.Row
                mastery_records = self._load_mastery_records(connection, normalized_student_id)
                mappings, mapping_available = self._load_ability_mappings(connection)
                if not mapping_available:
                    degradation_reasons.append("ability_mapping_unavailable")
                radar = self._build_radar(connection, normalized_student_id, mastery_records, mappings)
                overview = self._build_mastery_overview(mastery_records)
                weak_areas = self._build_weak_areas(connection, mastery_records)
                recent_progress = self._build_recent_progress(connection, normalized_student_id)
                resilience_metrics, resilience_fact_count = self._load_resilience(connection, normalized_student_id)
        except sqlite3.Error:
            mastery_records, mappings = [], {}
            radar = self._empty_radar()
            overview, weak_areas, recent_progress = self._build_mastery_overview([]), [], []
            resilience_metrics, resilience_fact_count = {}, 0
            degradation_reasons.append("sqlite_unavailable")

        self._apply_resilience(radar, resilience_metrics, resilience_fact_count)
        path_summary = self._learning_path_summary(normalized_student_id, degradation_reasons)
        has_facts = bool(mastery_records or resilience_fact_count)
        mapped_ids = {knowledge_id for knowledge_id, entries in mappings.items() if entries}
        mapping_missing_count = sum(record["knowledge_id"] not in mapped_ids for record in mastery_records)
        empty_state = None if has_facts else "暂无足够的学习记录，完成一次作答后将生成成长报告。"
        if not has_facts:
            radar["empty_state"] = "完成一次作答后生成能力雷达图。"
        response = {
            "student_id": normalized_student_id,
            "generated_at": datetime.now().isoformat(),
            "source": "growth_report_v1",
            "radar": radar,
            "mastery_overview": overview,
            "weak_knowledge_areas": weak_areas,
            "recent_progress": recent_progress,
            "learning_path_summary": path_summary,
            "empty_state": empty_state,
        }
        log_event(
            "growth_report.generated",
            student_id=normalized_student_id,
            report_version="growth_report_v1",
            mastery_record_count=len(mastery_records),
            resilience_fact_count=resilience_fact_count,
            dimension_sample_counts={item["id"]: item["sample_count"] for item in radar["dimensions"]},
            mapping_missing_count=mapping_missing_count,
            degradation_reasons=degradation_reasons,
        )
        return response

    @staticmethod
    def _load_mastery_records(connection: sqlite3.Connection, student_id: str) -> list[dict]:
        rows = connection.execute(
            """SELECT knowledge_id, COALESCE(master_level, 0) AS master_level,
                      COALESCE(priority, 0) AS priority, COALESCE(correct_count, 0) AS correct_count,
                      COALESCE(wrong_count, 0) AS wrong_count
               FROM knowledge_mastery WHERE student_id = ?""",
            (student_id,),
        ).fetchall()
        result = []
        for row in rows:
            raw_mastery = float(row["master_level"] or 0)
            result.append({
                "knowledge_id": str(row["knowledge_id"]),
                "mastery_level": max(0.0, min(raw_mastery * 100 if raw_mastery <= 1 else raw_mastery, 100.0)),
                "priority": max(0.0, float(row["priority"] or 0)),
                "correct_count": max(0, int(row["correct_count"] or 0)),
                "wrong_count": max(0, int(row["wrong_count"] or 0)),
            })
        return result

    @staticmethod
    def _load_ability_mappings(connection: sqlite3.Connection) -> tuple[dict[str, list[dict]], bool]:
        try:
            rows = connection.execute(
                "SELECT knowledge_id, dimension, weight FROM knowledge_ability_mapping WHERE mapping_version = ?",
                (MAPPING_VERSION,),
            ).fetchall()
        except sqlite3.Error:
            return {}, False
        mappings: dict[str, list[dict]] = {}
        for row in rows:
            mappings.setdefault(str(row["knowledge_id"]), []).append({
                "dimension": str(row["dimension"]), "weight": float(row["weight"]),
            })
        return mappings, True

    def _build_radar(self, connection: sqlite3.Connection, student_id: str, mastery_records: list[dict], mappings: dict[str, list[dict]]) -> dict:
        dimensions = []
        for dimension_id, label in ABILITY_DIMENSIONS:
            if dimension_id == "resilience":
                dimensions.append(self._dimension(dimension_id, label, None, 0, "none", "insufficient_data", "需要更多持续学习行为后生成评估。"))
                continue
            inputs = [(record, mapping["weight"]) for record in mastery_records for mapping in mappings.get(record["knowledge_id"], []) if mapping["dimension"] == dimension_id]
            if not inputs:
                dimensions.append(self._dimension(dimension_id, label, None, 0, "none", "insufficient_data", "暂无已映射的有效学习数据。"))
                continue
            score = sum(record["mastery_level"] * weight for record, weight in inputs) / sum(weight for _, weight in inputs)
            if dimension_id == "application":
                score = max(0.0, score - self._application_error_penalty(connection, student_id, {record["knowledge_id"] for record, _ in inputs}))
            sample_count = len({record["knowledge_id"] for record, _ in inputs})
            confidence = "high" if sample_count >= 5 else "medium" if sample_count >= 2 else "low"
            dimensions.append(self._dimension(dimension_id, label, round(score, 1), sample_count, confidence, "ready", self._score_summary(label, score)))
        return {"dimensions": dimensions, "empty_state": None}

    def _apply_resilience(self, radar: dict, metrics: dict[str, float | None], fact_count: int) -> None:
        resilience = next(item for item in radar["dimensions"] if item["id"] == "resilience")
        available = [value for value in metrics.values() if value is not None]
        if len(available) < 2:
            resilience.update({"sample_count": fact_count, "summary": "需要至少两类学习行为记录后生成韧性评估。"})
            return
        resilience.update({
            "score": round(sum(available) / len(available), 1), "sample_count": fact_count,
            "confidence": "high" if len(available) == 4 and fact_count >= 8 else "medium" if fact_count >= 4 else "low",
            "status": "ready", "summary": "根据订正、复习和近期持续学习行为计算。",
        })

    @staticmethod
    def _application_error_penalty(connection: sqlite3.Connection, student_id: str, knowledge_ids: set[str]) -> float:
        if not knowledge_ids:
            return 0.0
        try:
            placeholders = ",".join("?" for _ in knowledge_ids)
            rows = connection.execute(
                f"""SELECT ah.error_tags FROM answer_history ah JOIN question_knowledge_mapping qkm ON qkm.question_id = ah.question_id
                    WHERE ah.student_id = ? AND ah.is_correct = 0 AND qkm.knowledge_id IN ({placeholders})""",
                [student_id, *knowledge_ids],
            ).fetchall()
        except sqlite3.Error:
            return 0.0
        relevant = total = 0
        for row in rows:
            total += 1
            try:
                tags = json.loads(row["error_tags"] or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                tags = []
            if any(any(word in str(tag) for word in ("审题", "理解", "阅读", "应用")) for tag in tags):
                relevant += 1
        return min(15.0, 15.0 * relevant / total) if total else 0.0

    @staticmethod
    def _load_resilience(connection: sqlite3.Connection, student_id: str) -> tuple[dict[str, float | None], int]:
        metrics: dict[str, float | None] = {"correction": None, "continuation": None, "review": None, "consistency": None}
        fact_count = 0
        try:
            rows = connection.execute("SELECT current_status FROM mistake_case WHERE student_id = ?", (student_id,)).fetchall()
            fact_count += len(rows)
            if rows:
                metrics["correction"] = 100.0 * sum(row["current_status"] == "corrected" for row in rows) / len(rows)
        except sqlite3.Error:
            pass
        try:
            rows = connection.execute("""SELECT question_id, COUNT(*) AS attempts, MAX(is_correct) AS corrected FROM answer_history
                WHERE student_id = ? GROUP BY question_id HAVING SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) > 0""", (student_id,)).fetchall()
            fact_count += sum(int(row["attempts"]) for row in rows)
            if rows:
                metrics["continuation"] = 100.0 * sum(int(row["attempts"]) > 1 or bool(row["corrected"]) for row in rows) / len(rows)
        except sqlite3.Error:
            pass
        try:
            rows = connection.execute("SELECT status FROM review2_plan WHERE student_id = ?", (student_id,)).fetchall()
            fact_count += len(rows)
            if rows:
                metrics["review"] = 100.0 * sum(row["status"] == "completed" for row in rows) / len(rows)
        except sqlite3.Error:
            pass
        since = (datetime.now() - timedelta(days=13)).isoformat()
        try:
            rows = connection.execute("""SELECT substr(submitted_at, 1, 10) AS active_day FROM answer_history WHERE student_id = ? AND submitted_at >= ?
                UNION SELECT substr(ra.submitted_at, 1, 10) AS active_day FROM review2_attempt ra
                JOIN review2_session rs ON rs.id = ra.session_id WHERE rs.student_id = ? AND ra.submitted_at >= ?""", (student_id, since, student_id, since)).fetchall()
            active_days = {row["active_day"] for row in rows if row["active_day"]}
            if active_days:
                metrics["consistency"] = min(100.0, len(active_days) / 7 * 100)
        except sqlite3.Error:
            pass
        return metrics, fact_count

    @staticmethod
    def _build_mastery_overview(records: list[dict]) -> dict:
        levels = [record["mastery_level"] for record in records]
        return {"weak_count": sum(level < 60 for level in levels), "developing_count": sum(60 <= level < 80 for level in levels), "mastered_count": sum(level >= 80 for level in levels), "average_mastery": round(sum(levels) / len(levels), 1) if levels else None}

    @staticmethod
    def _build_weak_areas(connection: sqlite3.Connection, records: list[dict]) -> list[dict]:
        weak = sorted((record for record in records if record["mastery_level"] < 60), key=lambda record: record["mastery_level"])[:5]
        if not weak:
            return []
        names: dict[str, str] = {}
        try:
            placeholders = ",".join("?" for _ in weak)
            rows = connection.execute(f"SELECT knowledge_id, COALESCE(knowledge_name, knowledge_scope, knowledge_id) AS title FROM knowledge WHERE knowledge_id IN ({placeholders})", [record["knowledge_id"] for record in weak]).fetchall()
            names = {str(row["knowledge_id"]): str(row["title"]) for row in rows}
        except sqlite3.Error:
            pass
        return [{"knowledge_id": record["knowledge_id"], "title": names.get(record["knowledge_id"], record["knowledge_id"]), "mastery_level": round(record["mastery_level"], 1), "wrong_count": record["wrong_count"]} for record in weak]

    @staticmethod
    def _build_recent_progress(connection: sqlite3.Connection, student_id: str) -> list[dict]:
        since = (datetime.now() - timedelta(days=13)).isoformat()
        try:
            rows = connection.execute("""SELECT qkm.knowledge_id, COUNT(*) AS attempt_count, SUM(CASE WHEN ah.is_correct THEN 1 ELSE 0 END) AS correct_count
                FROM answer_history ah JOIN question_knowledge_mapping qkm ON qkm.question_id = ah.question_id
                WHERE ah.student_id = ? AND ah.submitted_at >= ? GROUP BY qkm.knowledge_id HAVING COUNT(*) > 0
                ORDER BY correct_count DESC, attempt_count DESC LIMIT 5""", (student_id, since)).fetchall()
        except sqlite3.Error:
            return []
        return [{"knowledge_id": str(row["knowledge_id"]), "attempt_count": int(row["attempt_count"]), "recent_correct_rate": round(100 * int(row["correct_count"] or 0) / int(row["attempt_count"]), 1)} for row in rows]

    def _learning_path_summary(self, student_id: str, degradation_reasons: list[str]) -> dict | None:
        try:
            path = self.path_recommender.generate_contract_path(student_id)
        except Exception:
            degradation_reasons.append("learning_path_summary_unavailable")
            return None
        nodes = path.get("data", [])
        return {"count": len(nodes), "first_knowledge_id": nodes[0]["knowledge_id"] if nodes else None}

    @staticmethod
    def _empty_radar() -> dict:
        return {"dimensions": [GrowthReportContractService._dimension(dimension_id, label, None, 0, "none", "unavailable", "能力数据暂时不可用。") for dimension_id, label in ABILITY_DIMENSIONS], "empty_state": None}

    @staticmethod
    def _dimension(dimension_id: str, label: str, score: float | None, sample_count: int, confidence: str, status: str, summary: str) -> dict:
        return {"id": dimension_id, "label": label, "score": score, "sample_count": sample_count, "confidence": confidence, "status": status, "summary": summary}

    @staticmethod
    def _score_summary(label: str, score: float) -> str:
        if score < 60:
            return f"{label}需要优先巩固。"
        if score < 80:
            return f"{label}正在稳步提升。"
        return f"{label}掌握较稳定。"
