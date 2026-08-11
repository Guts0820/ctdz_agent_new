import requests
from typing import List, Dict, Optional
from ..config import settings


class ReviewPlanClient:
    def __init__(self):
        self.base_url = settings.REVIEW_PLAN_SERVICE_URL
    
    def generate_review_plan(self, student_id: int) -> List[Dict]:
        try:
            response = requests.post(
                f"{self.base_url}/api/review/generate",
                json={"student_id": student_id},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("plan", [])
        except requests.exceptions.RequestException as e:
            return []
    
    def get_review_statistics(self) -> Dict:
        try:
            response = requests.get(
                f"{self.base_url}/api/review/stats",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "today_pending": 0,
                "week_completed": 0,
                "completion_rate": 0.0,
                "variant_ratio": 0.0
            }