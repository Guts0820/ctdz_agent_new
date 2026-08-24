from pydantic import BaseModel, Field
from typing import Optional, List, Any, Literal

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
    difficulty: Optional[str] = None
    textbook_version: Optional[str] = None
    unit: Optional[str] = None
    prerequisite: Optional[str] = None
    next_knowledge: Optional[str] = None
    is_core: Optional[bool] = None

class Question(BaseModel):
    id: Optional[str] = None
    text: Optional[str] = None
    answer: Optional[str] = None
    difficulty: Optional[Any] = None
    grade: Optional[int] = None
    semester: Optional[str] = None
    source: Optional[str] = None
    knowledge_id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    image_path: Optional[str] = None
    answer_steps: Optional[str] = None
    aliases: Optional[List[str]] = None
    explanation: Optional[str] = None
    fingerprint: Optional[str] = None
    status: Optional[str] = None
    standard_solution_status: Optional[str] = None
    llm_call_count: Optional[int] = None
    answer_source: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    llm_model: Optional[str] = None
    llm_solved_at: Optional[Any] = None


class QuestionCandidate(Question):
    retrieval_score: float
    match_type: str

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


class QuestionCandidateResponse(BaseModel):
    data: List[QuestionCandidate]
    total: int


class StandardAnswerItem(BaseModel):
    text: str = Field(min_length=1)
    explanation: str = ""
    answer: str = Field(min_length=1)
    request_id: Optional[str] = None
    grade: Optional[int] = None
    semester: Optional[str] = None
    difficulty: Optional[Any] = None
    answer_source: Optional[Literal["teacher", "llm"]] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    llm_model: Optional[str] = None
    llm_solved_at: Optional[str] = None
    llm_call_count: Optional[int] = None
    status: Literal["ready"] = "ready"
    standard_solution_status: Literal["ready"] = "ready"


class StandardAnswerUpsertRequest(BaseModel):
    items: List[StandardAnswerItem] = Field(min_length=1)


class StandardAnswerUpsertResult(BaseModel):
    request_id: Optional[str] = None
    question_id: str
    result: Literal["created", "updated"]


class StandardAnswerUpsertResponse(BaseModel):
    imported_count: int
    vectorized_count: int = 0
    questions: List[Question]
    results: List[StandardAnswerUpsertResult] = Field(default_factory=list)

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
