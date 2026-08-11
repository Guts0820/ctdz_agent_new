import sys
sys.path.append('.')

from typing import List, Dict
from ..models import GrowthReportData
from ..clients.review_plan_client import ReviewPlanClient
from ..core.learning_path import LearningPathRecommender
from mastery.api import get_five_dimension_scores, get_student_mastery_overview
from database import neo4j_conn


class DataAggregator:
    def __init__(self):
        self.review_plan_client = ReviewPlanClient()
        self.path_recommender = LearningPathRecommender()
    
    def _format_student_id(self, student_id: int) -> str:
        if isinstance(student_id, int):
            return f"S{student_id:03d}"
        return str(student_id)
    
    def generate_growth_report(self, student_id: int) -> GrowthReportData:
        five_dimension = get_five_dimension_scores(student_id)
        mastery_overview = get_student_mastery_overview(student_id)
        
        knowledge_list = mastery_overview.get("knowledge_list", [])
        
        weak_areas = []
        for item in knowledge_list:
            if item.get("mastery_level", 100) < 60:
                weak_areas.append({
                    "knowledge_id": item["knowledge_id"],
                    "title": item["title"],
                    "mastery_level": item["mastery_level"],
                    "suggestions": self._generate_suggestions(item)
                })
        weak_areas = sorted(weak_areas, key=lambda x: x["mastery_level"])[:5]
        
        recent_progress = self._get_recent_progress(student_id)
        
        learning_path = self.path_recommender.generate_path(student_id, limit=5)
        
        review_plan = self.review_plan_client.generate_review_plan(student_id)
        
        return GrowthReportData(
            student_id=student_id,
            five_dimension_scores=five_dimension.get("dimensions", []),
            weak_knowledge_areas=weak_areas,
            recent_progress=recent_progress,
            learning_path=learning_path,
            review_plan=review_plan if review_plan else None
        )
    
    def _generate_suggestions(self, knowledge_item: Dict) -> List[str]:
        suggestions = []
        mastery = knowledge_item.get("mastery_level", 100)
        
        if mastery < 40:
            suggestions.append("建议重新学习基础知识")
        elif mastery < 60:
            suggestions.append("建议多做练习题巩固")
        
        suggestions.append("查看错题解析")
        suggestions.append("复习相关先修知识")
        
        return suggestions
    
    def _get_recent_progress(self, student_id: int) -> List[Dict]:
        formatted_id = self._format_student_id(student_id)
        try:
            result = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:HAS_ANSWER]->(q:Question)-[:EXAMINES]->(kp:KnowledgePoint)
                RETURN kp.id as knowledge_id, kp.title as title,
                       sum(CASE WHEN a.is_correct = true THEN 1 ELSE 0 END) as correct_count,
                       count(a) as total_count
                ORDER BY kp.id
            """, {'student_id': formatted_id})
            
            progress_list = []
            for r in result:
                total = r['total_count']
                correct = r['correct_count']
                if total > 0:
                    improvement = correct / total * 100
                    progress_list.append({
                        "knowledge_id": r['knowledge_id'],
                        "title": r['title'],
                        "improvement": round(improvement, 1),
                        "correct_count": correct,
                        "total_count": total
                    })
            
            return sorted(progress_list, key=lambda x: x['improvement'], reverse=True)[:5]
        except Exception:
            return []
    
    def get_comprehensive_analysis(self, student_id: int) -> Dict:
        formatted_id = self._format_student_id(student_id)
        
        try:
            student_info = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})
                RETURN s.student_id as student_id, s.name as name, s.class_id as class_id
            """, {'student_id': formatted_id})
        except Exception:
            student_info = []
        
        try:
            mastery_summary = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[m:MASTERY]->(kp:KnowledgePoint)
                RETURN 
                    count(*) as total_knowledge,
                    sum(CASE WHEN m.mastery_level >= 80 THEN 1 ELSE 0 END) as mastered_count,
                    sum(CASE WHEN m.mastery_level >= 60 AND m.mastery_level < 80 THEN 1 ELSE 0 END) as improving_count,
                    sum(CASE WHEN m.mastery_level < 60 THEN 1 ELSE 0 END) as weak_count,
                    avg(m.mastery_level) as avg_mastery
            """, {'student_id': formatted_id})
        except Exception:
            mastery_summary = []
        
        try:
            recent_answers = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)
                RETURN 
                    count(*) as total_answers,
                    sum(CASE WHEN a.is_correct = true THEN 1 ELSE 0 END) as correct_count
            """, {'student_id': formatted_id})
        except Exception:
            recent_answers = []
        
        try:
            mistake_stats = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:FOR_MISTAKE]->(m:MistakeCase)
                WITH m
                RETURN count(*) as total_mistakes,
                       sum(CASE WHEN m.status = '已订正' THEN 1 ELSE 0 END) as corrected_count
            """, {'student_id': formatted_id})
        except Exception:
            mistake_stats = []
        
        return {
            'student': student_info[0] if student_info else {},
            'mastery_summary': mastery_summary[0] if mastery_summary else {},
            'answer_stats': recent_answers[0] if recent_answers else {},
            'mistake_stats': mistake_stats[0] if mistake_stats else {},
            'mistake_analysis': self.path_recommender.get_mistake_analysis(student_id),
            'learning_path': self.path_recommender.generate_detailed_path(student_id, limit=5)
        }