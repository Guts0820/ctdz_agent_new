from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class QuestionImportConfirmItem(BaseModel):
    item_id: str = Field(min_length=1)
    decision: Literal["teacher", "llm", "existing", "skip"]
    question_text: str | None = None
    teacher_answer: str | None = None
    teacher_explanation: str | None = None


class QuestionImportConfirmRequest(BaseModel):
    teacher_id: str = Field(min_length=1)
    items: list[QuestionImportConfirmItem] = Field(min_length=1)

    @model_validator(mode="after")
    def item_ids_must_be_unique(self) -> "QuestionImportConfirmRequest":
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("items 中不能包含重复 item_id")
        return self


class QuestionImportConfirmResult(BaseModel):
    item_id: str
    decision: Literal["teacher", "llm", "existing", "skip"]
    question_id: str | None = None
    result: Literal["created", "updated", "existing", "skipped"]


class QuestionImportConfirmResponse(BaseModel):
    import_id: str
    status: Literal["confirmed"]
    items: list[QuestionImportConfirmResult]


class TeacherQuestionListResponse(BaseModel):
    data: list[dict]
    total: int
    page: int
    page_size: int
