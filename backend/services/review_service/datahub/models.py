from datetime import datetime

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class LearningPathNode(BaseModel):
    knowledge_id: str
    title: str
    description: Optional[str] = ""
    order: int
    estimated_time: str = "45分钟"
    type: str = "normal"
    prerequisites: List[str] = []


class LearningPathResult(BaseModel):
    student_id: str
    path: List[LearningPathNode]


class LearningPathPrerequisite(BaseModel):
    knowledge_id: str
    title: str = ""


class LearningPathRecommendation(BaseModel):
    knowledge_id: str
    title: str
    sequence: int = Field(ge=1)
    stage: str
    mastery_level: float = Field(ge=0, le=100)
    priority: float = Field(ge=0)
    reason: str
    prerequisites: List[LearningPathPrerequisite] = Field(default_factory=list)
    estimated_minutes: int = Field(ge=1)
    next_action: str


class LearningPathResponse(BaseModel):
    student_id: str
    generated_at: datetime
    source: str
    data: List[LearningPathRecommendation] = Field(default_factory=list)
    empty_state: Optional[str] = None


class StatisticsOverview(BaseModel):
    total_students: int
    total_teachers: int
    total_questions: int
    total_knowledge: int
    total_wrong_records: int
    total_revision_completed: int


class ClassMasteryData(BaseModel):
    knowledge_id: str
    title: str
    average_mastery: float
    student_count: int


class ClassMasteryResult(BaseModel):
    class_id: int
    knowledge_list: List[ClassMasteryData]


class RevisionStatistics(BaseModel):
    today_pending: int
    week_completed: int
    completion_rate: float
    multiple_error_rate: float


class ReviewPlanStatistics(BaseModel):
    today_pending: int
    week_completed: int
    completion_rate: float
    variant_ratio: float


class GrowthReportData(BaseModel):
    student_id: str
    five_dimension_scores: List[Dict]
    weak_knowledge_areas: List[Dict]
    recent_progress: List[Dict]
    learning_path: List[LearningPathNode]
    review_plan: Optional[List[Dict]] = None


class RadarDimension(BaseModel):
    id: str
    label: str
    score: Optional[float] = Field(default=None, ge=0, le=100)
    sample_count: int = Field(ge=0)
    confidence: str
    status: str
    summary: str


class GrowthRadar(BaseModel):
    dimensions: List[RadarDimension] = Field(default_factory=list)
    empty_state: Optional[str] = None


class MasteryOverview(BaseModel):
    weak_count: int = Field(ge=0)
    developing_count: int = Field(ge=0)
    mastered_count: int = Field(ge=0)
    average_mastery: Optional[float] = Field(default=None, ge=0, le=100)


class LearningPathSummary(BaseModel):
    count: int = Field(ge=0)
    first_knowledge_id: Optional[str] = None


class GrowthReportResponse(BaseModel):
    student_id: str
    generated_at: datetime
    source: str
    radar: GrowthRadar
    mastery_overview: MasteryOverview
    weak_knowledge_areas: List[Dict] = Field(default_factory=list)
    recent_progress: List[Dict] = Field(default_factory=list)
    learning_path_summary: Optional[LearningPathSummary] = None
    empty_state: Optional[str] = None


class HighFrequencyWrongItem(BaseModel):
    question_id: str
    question_text: str
    error_rate: float
    total_count: int
    error_count: int


class ErrorAnalysisResult(BaseModel):
    student_id: int
    question_id: str
    error_type: str
    error_type_label: str
    error_detail: str
    related_knowledge: List[str]
