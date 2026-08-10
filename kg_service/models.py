from pydantic import BaseModel
from typing import Optional, List, Any

class KnowledgePoint(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    grade: Optional[int] = None
    semester: Optional[str] = None
    content: Optional[str] = None
    key_formulas: Optional[str] = None
    common_mistakes: Optional[str] = None
    teaching_points: Optional[str] = None

class Question(BaseModel):
    id: Optional[str] = None
    text: Optional[str] = None
    answer: Optional[str] = None
    difficulty: Optional[int] = None
    grade: Optional[int] = None
    semester: Optional[str] = None
    source: Optional[str] = None
    knowledge_id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    image_path: Optional[str] = None
    answer_steps: Optional[str] = None

class ErrorCause(BaseModel):
    id: Optional[str] = None
    level1: Optional[str] = None
    level2: Optional[str] = None
    level3: Optional[str] = None
    criteria: Optional[str] = None
    grade_range: Optional[str] = None
    knowledge_scope: Optional[str] = None
    example: Optional[str] = None
    name: Optional[str] = None

class KnowledgePointResponse(BaseModel):
    data: List[KnowledgePoint]
    total: int

class QuestionResponse(BaseModel):
    data: List[Question]
    total: int

class ErrorCauseResponse(BaseModel):
    data: List[ErrorCause]
    total: int

class RecommendRequest(BaseModel):
    knowledge_ids: List[str]
    count: Optional[int] = 5
    difficulty: Optional[str] = None

class RecommendResponse(BaseModel):
    recommended_questions: List[Question]
    related_knowledge_points: List[KnowledgePoint]

class AnalyzeRequest(BaseModel):
    question_ids: List[str]
    knowledge_ids: Optional[List[str]] = None

class WeakKnowledgePoint(BaseModel):
    knowledge_id: str
    title: str
    error_count: int
    related_questions_count: int

class AnalyzeResponse(BaseModel):
    weak_knowledge_points: List[WeakKnowledgePoint]
    recommended_review_plan: List[str]

class KnowledgeHierarchyNode(BaseModel):
    id: str
    title: str
    grade: Optional[int] = None
    children: Optional[List['KnowledgeHierarchyNode']] = None

KnowledgeHierarchyNode.update_forward_refs()