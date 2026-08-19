import sqlite3
from datetime import datetime
from typing import List, Optional
from .calculator import ExerciseRecord, KnowledgePoint


class MasteryDatabase:
    def __init__(self, db_path: str = "database/sqlite/learning_data.db"):
        self.db_path = db_path
    
    def _connect(self):
        return sqlite3.connect(self.db_path)
    
    def get_student_exercise_records(self, student_id: int, knowledge_id: Optional[str] = None) -> List[ExerciseRecord]:
        conn = self._connect()
        cursor = conn.cursor()
        
        if knowledge_id:
            cursor.execute('''
                SELECT timestamp, is_correct, error_causes 
                FROM exercise_records 
                WHERE student_id = ? AND knowledge_id = ? 
                ORDER BY timestamp
            ''', (student_id, knowledge_id))
        else:
            cursor.execute('''
                SELECT timestamp, is_correct, error_causes 
                FROM exercise_records 
                WHERE student_id = ? 
                ORDER BY timestamp
            ''', (student_id,))
        
        records = []
        for row in cursor.fetchall():
            timestamp = datetime.fromisoformat(row[0]) if row[0] else datetime.now()
            is_correct = bool(row[1])
            error_causes = row[2].split('|') if row[2] else []
            
            records.append(ExerciseRecord(
                timestamp=timestamp,
                is_correct=is_correct,
                error_causes=error_causes
            ))
        
        conn.close()
        return records
    
    def get_student_knowledge_points(self, student_id: int) -> List[KnowledgePoint]:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT er.knowledge_id, k.title, k.importance
            FROM exercise_records er
            LEFT JOIN knowledge_points k ON er.knowledge_id = k.knowledge_id
            WHERE er.student_id = ?
        ''', (student_id,))
        
        points = []
        for row in cursor.fetchall():
            points.append(KnowledgePoint(
                knowledge_id=row[0],
                title=row[1] if row[1] else row[0],
                importance=row[2] if row[2] else 0.8
            ))
        
        conn.close()
        return points
    
    def get_all_knowledge_points(self) -> List[KnowledgePoint]:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT knowledge_id, title, importance FROM knowledge_points
        ''')
        
        points = []
        for row in cursor.fetchall():
            points.append(KnowledgePoint(
                knowledge_id=row[0],
                title=row[1],
                importance=row[2] if row[2] else 0.8
            ))
        
        conn.close()
        return points
    
    def get_students_in_class(self, class_id: int) -> List[int]:
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id FROM users WHERE class_id = ? AND role = 'student'
        ''', (class_id,))
        
        students = [row[0] for row in cursor.fetchall()]
        conn.close()
        return students
    
    def add_exercise_record(self, student_id: int, knowledge_id: str, is_correct: bool, 
                           error_causes: List[str] = None, timestamp: Optional[datetime] = None):
        conn = self._connect()
        cursor = conn.cursor()
        
        error_causes_str = '|'.join(error_causes) if error_causes else ''
        timestamp_str = timestamp.isoformat() if timestamp else datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO exercise_records (student_id, knowledge_id, is_correct, error_causes, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, knowledge_id, is_correct, error_causes_str, timestamp_str))
        
        conn.commit()
        conn.close()
    
    def create_tables(self):
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exercise_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                knowledge_id TEXT,
                is_correct INTEGER,
                error_causes TEXT,
                timestamp TEXT,
                FOREIGN KEY (student_id) REFERENCES users(user_id),
                FOREIGN KEY (knowledge_id) REFERENCES knowledge_points(knowledge_id)
            )
        ''')
        
        conn.commit()
        conn.close()
