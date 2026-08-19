import sys
sys.path.append('.')

import sqlite3
from typing import List, Dict
from ..models import StatisticsOverview, ClassMasteryData, RevisionStatistics
from ..clients.review_plan_client import ReviewPlanClient
from backend.services.review_service.mastery.api import get_class_average_mastery


class StatisticsReporter:
    def __init__(self):
        self.review_plan_client = ReviewPlanClient()
    
    def _connect(self):
        return sqlite3.connect('database/sqlite/learning_data.db')
    
    def get_system_overview(self) -> StatisticsOverview:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(DISTINCT student_id) FROM exercise_records")
        total_students = cursor.fetchone()[0]
        
        total_teachers = 1
        
        cursor.execute("SELECT COUNT(*) FROM knowledge_points")
        total_knowledge = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exercise_records WHERE is_correct = 0")
        total_wrong_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exercise_records WHERE is_correct = 1")
        total_correct = cursor.fetchone()[0]
        
        conn.close()
        
        return StatisticsOverview(
            total_students=total_students,
            total_teachers=total_teachers,
            total_questions=total_correct + total_wrong_records,
            total_knowledge=total_knowledge,
            total_wrong_records=total_wrong_records,
            total_revision_completed=total_correct
        )
    
    def get_class_mastery(self, class_id: int) -> List[ClassMasteryData]:
        result = get_class_average_mastery(class_id)
        knowledge_list = result.get("knowledge_list", [])
        
        return [
            ClassMasteryData(
                knowledge_id=item["knowledge_id"],
                title=item["title"],
                average_mastery=item["average_mastery"],
                student_count=item["student_count"]
            )
            for item in knowledge_list
        ]
    
    def get_revision_statistics(self) -> RevisionStatistics:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM exercise_records WHERE is_correct = 0")
        total_wrong = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM exercise_records WHERE is_correct = 1")
        total_correct = cursor.fetchone()[0]
        
        completion_rate = total_correct / (total_correct + total_wrong) if (total_correct + total_wrong) > 0 else 0.0
        
        conn.close()
        
        return RevisionStatistics(
            today_pending=total_wrong,
            week_completed=total_correct,
            completion_rate=round(completion_rate * 100, 1),
            multiple_error_rate=25.0
        )
    
    def get_review_plan_statistics(self) -> Dict:
        return self.review_plan_client.get_review_statistics()
    
    def get_grade_distribution(self) -> Dict:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT student_id, COUNT(*) FROM exercise_records GROUP BY student_id")
        distribution = {}
        for i, row in enumerate(cursor.fetchall()):
            grade = f"五年级"
            if grade not in distribution:
                distribution[grade] = 0
            distribution[grade] += 1
        
        conn.close()
        return distribution
