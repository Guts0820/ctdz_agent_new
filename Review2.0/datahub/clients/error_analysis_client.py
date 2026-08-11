import requests
from typing import List, Dict
from ..config import settings


class ErrorAnalysisClient:
    def __init__(self):
        self.base_url = settings.ERROR_ANALYSIS_SERVICE_URL
    
    def analyze_error(self, student_id: int, question_id: str, 
                     student_answer: str, correct_answer: str) -> Dict:
        try:
            response = requests.post(
                f"{self.base_url}/api/error/analyze",
                json={
                    "student_id": student_id,
                    "question_id": question_id,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": str(e),
                "error_type": "unknown",
                "error_type_label": "未知",
                "error_detail": "",
                "related_knowledge": []
            }
    
    def get_high_frequency_wrong(self, class_id: int, limit: int = 5) -> List[Dict]:
        try:
            response = requests.post(
                f"{self.base_url}/api/error/high_frequency",
                json={"class_id": class_id, "limit": limit},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("wrong_questions", [])
        except requests.exceptions.RequestException as e:
            return []