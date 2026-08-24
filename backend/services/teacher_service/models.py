from typing import Literal

from pydantic import BaseModel, Field


class CreateBatchRequest(BaseModel):
    class_id: str
    teacher_id: str
    batch_date: str
    question_ids: list[str]


class ReleasePartialRequest(BaseModel):
    question_ids: list[str]


class BatchResponse(BaseModel):
    batch_id: str
    class_id: str
    teacher_id: str
    batch_date: str
    release_status: str
    question_count: int
    question_ids: list[str] = []


class BatchListResponse(BaseModel):
    data: list[BatchResponse]
    total: int


class ManualReviewRequest(BaseModel):
    decision: str
    comment: str = ""


class QuestionImportPreviewItem(BaseModel):
    item_id: str
    position: int
    question_text: str
    teacher_answer: str
    teacher_explanation: str = ""
    llm_answer: str | None = None
    llm_solve_steps: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    solution_source: Literal["llm", "existing", "none"] = "none"
    comparison_status: Literal["agreed", "conflict", "uncertain", "llm_failed"]
    comparison_reason: str
    comparison_confidence: float = Field(ge=0, le=1)
    existing_question_id: str | None = None


class QuestionImportPreviewResponse(BaseModel):
    import_id: str
    teacher_id: str
    grade: int
    semester: str | None = None
    status: Literal["review_required"]
    ocr_confidence: float | None = None
    ocr_engine: str | None = None
    items: list[QuestionImportPreviewItem]
