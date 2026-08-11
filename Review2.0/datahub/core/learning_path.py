import sys
sys.path.append('.')

from typing import List, Dict, Optional
from ..models import LearningPathNode
from database import neo4j_conn


class LearningPathRecommender:
    def __init__(self):
        pass
    
    def _format_student_id(self, student_id: int) -> str:
        if isinstance(student_id, int):
            return f"S{student_id:03d}"
        return str(student_id)
    
    def _get_weak_knowledge_from_neo4j(self, student_id: int) -> List[Dict]:
        formatted_id = self._format_student_id(student_id)
        try:
            result = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[m:MASTERY]->(kp:KnowledgePoint)
                WHERE m.mastery_level < 60
                RETURN kp.id as knowledge_id, kp.title as title, kp.grade as grade, 
                       kp.semester as semester, m.mastery_level as mastery_level,
                       m.mastery_level_str as mastery_level_str,
                       m.correct_streak as correct_streak, m.wrong_streak as wrong_streak
                ORDER BY m.mastery_level ASC
                LIMIT 10
            """, {'student_id': formatted_id})
            return result
        except Exception:
            return []
    
    def _get_prerequisites(self, knowledge_id: str) -> List[str]:
        try:
            result = neo4j_conn.query("""
                MATCH (prereq:KnowledgePoint)-[:PREREQUISITE_OF]->(kp:KnowledgePoint {id: $knowledge_id})
                RETURN prereq.id as id, prereq.title as title
                ORDER BY prereq.id
            """, {'knowledge_id': knowledge_id})
            return [f"{r['id']}: {r['title']}" for r in result]
        except Exception:
            return []
    
    def _get_related_knowledge(self, knowledge_id: str) -> Dict[str, List[str]]:
        related = {'prerequisites': [], 'extension': [], 'application': [], 'confusion': []}
        
        try:
            prereq_result = neo4j_conn.query("""
                MATCH (prereq:KnowledgePoint)-[:PREREQUISITE_OF]->(kp:KnowledgePoint {id: $knowledge_id})
                RETURN prereq.id as id, prereq.title as title, '前置基础' as rel_type
                ORDER BY prereq.id
            """, {'knowledge_id': knowledge_id})
            related['prerequisites'] = [f"{r['id']}: {r['title']}" for r in prereq_result]
        except Exception:
            pass
        
        try:
            extension_result = neo4j_conn.query("""
                MATCH (kp:KnowledgePoint {id: $knowledge_id})-[:EXTENDS_TO]->(ext:KnowledgePoint)
                RETURN ext.id as id, ext.title as title, '延伸拓展' as rel_type
                ORDER BY ext.id
            """, {'knowledge_id': knowledge_id})
            related['extension'] = [f"{r['id']}: {r['title']}" for r in extension_result]
        except Exception:
            pass
        
        try:
            app_result = neo4j_conn.query("""
                MATCH (kp:KnowledgePoint {id: $knowledge_id})-[:SUPPORTS]->(app:KnowledgePoint)
                RETURN app.id as id, app.title as title, '应用支撑' as rel_type
                ORDER BY app.id
            """, {'knowledge_id': knowledge_id})
            related['application'] = [f"{r['id']}: {r['title']}" for r in app_result]
        except Exception:
            pass
        
        try:
            confusion_result = neo4j_conn.query("""
                MATCH (kp:KnowledgePoint {id: $knowledge_id})-[r]->(conf:KnowledgePoint)
                WHERE type(r) IN ['EQUIVALENT_TO', 'DERIVES_FROM']
                RETURN conf.id as id, conf.title as title, type(r) as rel_type
                ORDER BY conf.id
            """, {'knowledge_id': knowledge_id})
            related['confusion'] = [f"{r['id']}: {r['title']}({r['rel_type']})" for r in confusion_result]
        except Exception:
            pass
        
        return related
    
    def _get_questions_for_knowledge(self, knowledge_id: str, difficulty: int = 0, limit: int = 5) -> List[Dict]:
        try:
            query = """
                MATCH (q:Question)
                WHERE q.knowledge_id = $knowledge_id
            """
            params = {'knowledge_id': knowledge_id}
            
            if difficulty > 0:
                query += " AND q.difficulty = $difficulty"
                params['difficulty'] = difficulty
            
            query += """
                RETURN q.id as id, q.text as text, q.answer as answer, 
                       q.difficulty as difficulty, q.type as type,
                       q.image_path as image_path, q.answer_steps as answer_steps
                ORDER BY q.difficulty ASC
                LIMIT $limit
            """
            params['limit'] = limit
            
            result = neo4j_conn.query(query, params)
            return result
        except Exception:
            return []
    
    def _get_mistakes_for_knowledge(self, knowledge_id: str, student_id: int = 0) -> List[Dict]:
        try:
            formatted_id = self._format_student_id(student_id) if student_id else None
            
            if formatted_id:
                result = neo4j_conn.query("""
                    MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:FOR_MISTAKE]->(m:MistakeCase)-[:FOR_QUESTION]->(q:Question)
                    WHERE q.knowledge_id = $knowledge_id
                    MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                    RETURN m.mistake_case_id as mistake_id, q.id as question_id, 
                           q.text as question_text, e.name as error_name, e.id as error_id,
                           m.status as status, a.answer as student_answer, q.answer as correct_answer
                    ORDER BY m.created_at DESC
                    LIMIT 10
                """, {'student_id': formatted_id, 'knowledge_id': knowledge_id})
            else:
                result = neo4j_conn.query("""
                    MATCH (m:MistakeCase)-[:FOR_QUESTION]->(q:Question)
                    WHERE q.knowledge_id = $knowledge_id
                    OPTIONAL MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                    RETURN m.mistake_case_id as mistake_id, q.id as question_id, 
                           q.text as question_text, e.name as error_name, e.id as error_id,
                           m.status as status
                    ORDER BY m.created_at DESC
                    LIMIT 10
                """, {'knowledge_id': knowledge_id})
            
            return result
        except Exception:
            return []
    
    def _get_error_causes_for_knowledge(self, knowledge_id: str) -> List[Dict]:
        try:
            result = neo4j_conn.query("""
                MATCH (q:Question)-[:EXAMINES]->(kp:KnowledgePoint {id: $knowledge_id})
                MATCH (m:MistakeCase)-[:FOR_QUESTION]->(q)
                MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                RETURN e.id as error_id, e.name as error_name, e.description as description,
                       count(m) as occurrence_count
                ORDER BY occurrence_count DESC
                LIMIT 10
            """, {'knowledge_id': knowledge_id})
            return result
        except Exception:
            return []
    
    def _get_error_categories_for_knowledge(self, knowledge_id: str) -> List[Dict]:
        try:
            result = neo4j_conn.query("""
                MATCH (q:Question)-[:EXAMINES]->(kp:KnowledgePoint {id: $knowledge_id})
                MATCH (m:MistakeCase)-[:FOR_QUESTION]->(q)
                MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                WITH e, count(m) as cnt
                CASE 
                    WHEN e.id STARTS WITH 'C' THEN '计算错误'
                    WHEN e.id STARTS WITH 'I' THEN '抄写错误'
                    WHEN e.id STARTS WITH 'L' THEN '逻辑错误'
                    WHEN e.id STARTS WITH 'P' THEN '概念错误'
                    WHEN e.id STARTS WITH 'S' THEN '审题错误'
                    ELSE '其他'
                END as category
                RETURN category, sum(cnt) as total_count
                ORDER BY total_count DESC
            """, {'knowledge_id': knowledge_id})
            return result
        except Exception:
            return []
    
    def _get_student_mistake_stats(self, student_id: int) -> Dict:
        formatted_id = self._format_student_id(student_id)
        try:
            result = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:FOR_MISTAKE]->(m:MistakeCase)
                OPTIONAL MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                WITH e, count(m) as mistake_count
                RETURN 
                    sum(CASE WHEN e.id STARTS WITH 'C' THEN mistake_count ELSE 0 END) as calc_errors,
                    sum(CASE WHEN e.id STARTS WITH 'I' THEN mistake_count ELSE 0 END) as copy_errors,
                    sum(CASE WHEN e.id STARTS WITH 'L' THEN mistake_count ELSE 0 END) as logic_errors,
                    sum(CASE WHEN e.id STARTS WITH 'P' THEN mistake_count ELSE 0 END) as concept_errors,
                    sum(CASE WHEN e.id STARTS WITH 'S' THEN mistake_count ELSE 0 END) as reading_errors,
                    sum(mistake_count) as total_mistakes
            """, {'student_id': formatted_id})
            
            if result:
                return result[0]
            return {'calc_errors': 0, 'copy_errors': 0, 'logic_errors': 0, 
                    'concept_errors': 0, 'reading_errors': 0, 'total_mistakes': 0}
        except Exception:
            return {'calc_errors': 0, 'copy_errors': 0, 'logic_errors': 0, 
                    'concept_errors': 0, 'reading_errors': 0, 'total_mistakes': 0}
    
    def _get_pending_review_tasks(self, student_id: int) -> List[Dict]:
        formatted_id = self._format_student_id(student_id)
        try:
            result = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:HAS_REVIEW_PLAN]->(r:ReviewPlan)
                WHERE r.status = '进行中'
                RETURN r.review_plan_id as plan_id, r.plan_details as details, 
                       r.priority as priority, r.target_date as due_date
                ORDER BY 
                    CASE r.priority 
                        WHEN '高' THEN 1 
                        WHEN '中' THEN 2 
                        WHEN '低' THEN 3 
                    END,
                    r.target_date ASC
                LIMIT 10
            """, {'student_id': formatted_id})
            return result
        except Exception:
            return []
    
    def _get_push_records(self, student_id: int, completed: bool = False) -> List[Dict]:
        formatted_id = self._format_student_id(student_id)
        try:
            if completed:
                result = neo4j_conn.query("""
                    MATCH (s:Student {student_id: $student_id})-[:HAS_PUSH]->(p:PushRecord)
                    WHERE p.status = '已完成'
                    RETURN p.push_record_id as push_id, p.push_stage as stage, 
                           p.push_date as date, p.status as status
                    ORDER BY p.push_date DESC
                    LIMIT 10
                """, {'student_id': formatted_id})
            else:
                result = neo4j_conn.query("""
                    MATCH (s:Student {student_id: $student_id})-[:HAS_PUSH]->(p:PushRecord)
                    WHERE p.status IN ['待推送', '推送中']
                    RETURN p.push_record_id as push_id, p.push_stage as stage, 
                           p.push_date as date, p.status as status
                    ORDER BY p.push_date ASC
                    LIMIT 10
                """, {'student_id': formatted_id})
            return result
        except Exception:
            return []
    
    def _get_recommended_questions(self, student_id: int, knowledge_id: str, mastery_level: int = 0) -> List[Dict]:
        if mastery_level < 30:
            difficulty = 1
        elif mastery_level < 60:
            difficulty = 2
        else:
            difficulty = 3
        
        basic_questions = self._get_questions_for_knowledge(knowledge_id, difficulty=difficulty, limit=3)
        
        extension_questions = self._get_questions_for_knowledge(knowledge_id, difficulty=min(difficulty + 1, 5), limit=2)
        
        return basic_questions + extension_questions
    
    def generate_path(self, student_id: int, limit: int = 5) -> List[Dict]:
        formatted_id = self._format_student_id(student_id)
        weak_knowledge = self._get_weak_knowledge_from_neo4j(student_id)
        student_mistake_stats = self._get_student_mistake_stats(student_id)
        pending_reviews = self._get_pending_review_tasks(student_id)
        
        path_nodes = []
        
        if weak_knowledge:
            for weak in weak_knowledge[:limit]:
                knowledge_id = weak['knowledge_id']
                title = weak['title']
                mastery_level = weak['mastery_level']
                prerequisites = self._get_prerequisites(knowledge_id)
                related = self._get_related_knowledge(knowledge_id)
                questions = self._get_recommended_questions(student_id, knowledge_id, mastery_level)
                mistakes = self._get_mistakes_for_knowledge(knowledge_id, student_id)
                error_analysis = self._get_error_causes_for_knowledge(knowledge_id)
                error_categories = self._get_error_categories_for_knowledge(knowledge_id)
                
                type_label = "weak" if mastery_level < 40 else "learning"
                
                time_estimate = "45分钟" if mastery_level < 40 else "30分钟"
                
                path_nodes.append({
                    'knowledge_id': knowledge_id,
                    'title': title,
                    'mastery_level': mastery_level,
                    'order': len(path_nodes) + 1,
                    'estimated_time': time_estimate,
                    'type': type_label,
                    'prerequisites': prerequisites,
                    'related_knowledge': related,
                    'recommended_questions': questions,
                    'mistakes': mistakes,
                    'error_analysis': error_analysis,
                    'error_categories': error_categories,
                    'suggestions': self._generate_learning_suggestions(
                        mastery_level, prerequisites, error_categories, student_mistake_stats
                    )
                })
        
        if len(path_nodes) < limit:
            needed = limit - len(path_nodes)
            
            try:
                completed_result = neo4j_conn.query("""
                    MATCH (s:Student {student_id: $student_id})-[m:MASTERY]->(kp:KnowledgePoint)
                    RETURN kp.id as knowledge_id, kp.title as title, m.mastery_level as mastery_level
                    ORDER BY m.mastery_level DESC
                    LIMIT $limit
                """, {'student_id': formatted_id, 'limit': needed})
                
                for item in completed_result:
                    if item['knowledge_id'] not in [n['knowledge_id'] for n in path_nodes]:
                        knowledge_id = item['knowledge_id']
                        mastery_level = item['mastery_level']
                        prerequisites = self._get_prerequisites(knowledge_id)
                        related = self._get_related_knowledge(knowledge_id)
                        
                        path_nodes.append({
                            'knowledge_id': knowledge_id,
                            'title': item['title'],
                            'mastery_level': mastery_level,
                            'order': len(path_nodes) + 1,
                            'estimated_time': "30分钟",
                            'type': "review",
                            'prerequisites': prerequisites,
                            'related_knowledge': related,
                            'recommended_questions': [],
                            'mistakes': [],
                            'error_analysis': [],
                            'error_categories': [],
                            'suggestions': ['复习巩固已学知识', '做几道练习题保持熟练度']
                        })
            except Exception:
                pass
        
        return path_nodes
    
    def _generate_learning_suggestions(self, mastery_level: int, prerequisites: List, 
                                        error_categories: List, student_stats: Dict) -> List[str]:
        suggestions = []
        
        if mastery_level < 30:
            suggestions.append("建议从基础概念开始重新学习")
            suggestions.append("观看知识点讲解视频")
            suggestions.append("完成基础难度的练习题")
        elif mastery_level < 50:
            suggestions.append("回顾重点概念和公式")
            suggestions.append("完成中等难度的练习题")
            if prerequisites:
                suggestions.append(f"建议先复习前置知识: {prerequisites[0]}")
        else:
            suggestions.append("加强应用练习")
            suggestions.append("尝试变式题和综合题")
        
        if error_categories:
            categories_str = '、'.join([c['category'] for c in error_categories[:3]])
            suggestions.append(f"重点关注易错类型: {categories_str}")
        
        if student_stats.get('calc_errors', 0) > student_stats.get('total_mistakes', 1) * 0.3:
            suggestions.append("注意计算过程的准确性，养成检查习惯")
        
        if student_stats.get('reading_errors', 0) > student_stats.get('total_mistakes', 1) * 0.2:
            suggestions.append("加强审题能力，仔细阅读题目要求")
        
        if student_stats.get('logic_errors', 0) > student_stats.get('total_mistakes', 1) * 0.2:
            suggestions.append("注重解题思路和逻辑推理的培养")
        
        return suggestions
    
    def generate_detailed_path(self, student_id: int, limit: int = 5) -> Dict:
        path_nodes = self.generate_path(student_id, limit)
        
        student_mistake_stats = self._get_student_mistake_stats(student_id)
        pending_reviews = self._get_pending_review_tasks(student_id)
        completed_pushes = self._get_push_records(student_id, completed=True)
        pending_pushes = self._get_push_records(student_id, completed=False)
        
        return {
            "student_id": student_id,
            "path": path_nodes,
            "total_nodes": len(path_nodes),
            "student_error_profile": student_mistake_stats,
            "pending_reviews": pending_reviews,
            "completed_pushes": completed_pushes,
            "pending_pushes": pending_pushes
        }
    
    def get_knowledge_detail(self, knowledge_id: str) -> Dict:
        try:
            knowledge = neo4j_conn.query("""
                MATCH (kp:KnowledgePoint {id: $knowledge_id})
                RETURN kp.id as id, kp.title as title, kp.grade as grade, 
                       kp.semester as semester
            """, {'knowledge_id': knowledge_id})
            
            if not knowledge:
                return {}
            
            k = knowledge[0]
            
            prerequisites = self._get_prerequisites(knowledge_id)
            related = self._get_related_knowledge(knowledge_id)
            questions = self._get_questions_for_knowledge(knowledge_id, limit=10)
            error_analysis = self._get_error_causes_for_knowledge(knowledge_id)
            error_categories = self._get_error_categories_for_knowledge(knowledge_id)
            
            return {
                'id': k['id'],
                'title': k['title'],
                'grade': k['grade'],
                'semester': k['semester'],
                'prerequisites': prerequisites,
                'related_knowledge': related,
                'questions': questions,
                'error_analysis': error_analysis,
                'error_categories': error_categories
            }
        except Exception:
            return {}
    
    def get_mistake_analysis(self, student_id: int) -> Dict:
        formatted_id = self._format_student_id(student_id)
        
        mistake_stats = self._get_student_mistake_stats(student_id)
        
        try:
            knowledge_mistakes = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:FOR_MISTAKE]->(m:MistakeCase)-[:FOR_QUESTION]->(q:Question)-[:EXAMINES]->(kp:KnowledgePoint)
                MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                RETURN kp.id as knowledge_id, kp.title as knowledge_title, 
                       e.name as error_name, e.id as error_id, count(*) as mistake_count
                ORDER BY mistake_count DESC
                LIMIT 20
            """, {'student_id': formatted_id})
        except Exception:
            knowledge_mistakes = []
        
        try:
            recent_mistakes = neo4j_conn.query("""
                MATCH (s:Student {student_id: $student_id})-[:ANSWERS_QUESTION]->(a:AnswerHistory)-[:FOR_MISTAKE]->(m:MistakeCase)-[:FOR_QUESTION]->(q:Question)
                OPTIONAL MATCH (m)-[:HAS_ERROR_CAUSE]->(e:ErrorCause)
                RETURN q.id as question_id, q.text as question_text, e.name as error_name,
                       a.answer as student_answer, q.answer as correct_answer,
                       m.created_at as mistake_date, m.status as status
                ORDER BY m.created_at DESC
                LIMIT 10
            """, {'student_id': formatted_id})
        except Exception:
            recent_mistakes = []
        
        return {
            'student_id': student_id,
            'total_mistakes': mistake_stats.get('total_mistakes', 0),
            'error_distribution': {
                'calculation': mistake_stats.get('calc_errors', 0),
                'copy': mistake_stats.get('copy_errors', 0),
                'logic': mistake_stats.get('logic_errors', 0),
                'concept': mistake_stats.get('concept_errors', 0),
                'reading': mistake_stats.get('reading_errors', 0)
            },
            'knowledge_mistakes': knowledge_mistakes,
            'recent_mistakes': recent_mistakes
        }