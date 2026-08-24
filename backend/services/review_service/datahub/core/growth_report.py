"""Growth-report contract service. Scoring is introduced in the next implementation stage."""

import sqlite3
from datetime import datetime

from backend.shared.config import DATABASE_PATH
from .ability_mapping import ABILITY_DIMENSIONS
from .learning_path import normalize_student_id


class GrowthReportContractService:
    """Return stable report states without inventing radar scores before aggregation exists."""

    def generate_contract_report(self, student_id: str | int) -> dict:
        normalized_student_id = normalize_student_id(student_id)
        has_mastery_facts = self._has_mastery_facts(normalized_student_id)
        dimensions = [
            {
                "id": dimension_id,
                "label": label,
                "score": None,
                "sample_count": 0,
                "confidence": "none",
                "status": "insufficient_data",
                "summary": "完成更多相关学习后可生成能力评估。",
            }
            for dimension_id, label in ABILITY_DIMENSIONS
        ]
        return {
            "student_id": normalized_student_id,
            "generated_at": datetime.now().isoformat(),
            "source": "growth_report_v1",
            "radar": {
                "dimensions": dimensions,
                "empty_state": "完成一次作答后生成能力雷达图。" if not has_mastery_facts else None,
            },
            "mastery_overview": {
                "weak_count": 0,
                "developing_count": 0,
                "mastered_count": 0,
                "average_mastery": None,
            },
            "weak_knowledge_areas": [],
            "recent_progress": [],
            "learning_path_summary": None,
            "empty_state": "暂无足够的学习记录，完成一次作答后将生成成长报告。" if not has_mastery_facts else None,
        }

    @staticmethod
    def _has_mastery_facts(student_id: str) -> bool:
        try:
            with sqlite3.connect(DATABASE_PATH) as connection:
                return connection.execute(
                    "SELECT 1 FROM knowledge_mastery WHERE student_id = ? LIMIT 1",
                    (student_id,),
                ).fetchone() is not None
        except sqlite3.Error:
            return False
