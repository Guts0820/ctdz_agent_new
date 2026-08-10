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
    ocr_text: Optional[str] = None
    visual_description: Optional[str] = None
    image_embedding: Optional[List[float]] = None

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

class User(BaseModel):
    id: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    grade: Optional[int] = None
    semester: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class WrongQuestion(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    question_id: Optional[str] = None
    wrong_answer: Optional[str] = None
    error_cause_id: Optional[str] = None
    wrong_count: Optional[int] = None
    last_wrong_time: Optional[str] = None
    reviewed: Optional[bool] = None
    reviewed_at: Optional[str] = None

class LearningProgress(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    knowledge_id: Optional[str] = None
    mastery_level: Optional[int] = None
    correct_count: Optional[int] = None
    wrong_count: Optional[int] = None
    last_practice_time: Optional[str] = None

class AnswerRecord(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    question_id: Optional[str] = None
    answer: Optional[str] = None
    is_correct: Optional[bool] = None
    time_spent: Optional[int] = None
    answered_at: Optional[str] = None

class ReviewPlan(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    question_id: Optional[str] = None
    review_time: Optional[str] = None
    priority: Optional[int] = None
    completed: Optional[bool] = None

class VisualSearchRequest(BaseModel):
    query_type: str = "text"
    query: str = ""
    question_id: Optional[str] = None
    top_k: Optional[int] = 5
    grade: Optional[int] = None
    semester: Optional[str] = None

class SimilarQuestion(BaseModel):
    question: Question
    similarity: float

class VisualSearchResponse(BaseModel):
    results: List[SimilarQuestion]

class FiveDimensionScore(BaseModel):
    dimension: str
    score: int
    max_score: int = 100
    label: str

class WeakKnowledgeArea(BaseModel):
    knowledge_id: str
    title: str
    mastery_level: int
    error_count: int
    difficulty: str
    suggestions: List[str]

class ProgressItem(BaseModel):
    knowledge_id: str
    title: str
    previous_mastery: int
    current_mastery: int
    improvement: int
    achieved: bool
    achieved_at: Optional[str]

class LearningPathNode(BaseModel):
    knowledge_id: str
    title: str
    description: str
    order: int
    estimated_time: str
    type: str
    prerequisites: List[str]

class GrowthReport(BaseModel):
    user_id: int
    username: str
    grade: int
    semester: str
    report_date: str
    five_dimension_scores: List[FiveDimensionScore]
    weak_knowledge_areas: List[WeakKnowledgeArea]
    recent_progress: List[ProgressItem]
    learning_path: List[LearningPathNode]