from typing import Optional

from pydantic import BaseModel


class SubmitRequest(BaseModel):
    student_id: str
    batch_id: Optional[str] = None
    question_id: Optional[str] = None
    image: Optional[str] = None
    original_question: Optional[str] = None
    student_write: Optional[str] = None
    grade: Optional[str] = "三年级"


class SubmitResponse(BaseModel):
    status: str
    data: dict


class MistakeCorrectionRequest(BaseModel):
    original_question: str
    new_answer: str


class MistakeCorrectionResponse(BaseModel):
    mistake_case_id: str
    answer_history_id: str
    question_id: str
    original_question: str
    new_answer: str
    judge_result: str
    is_correct: bool
    mistake_status: str
    teaching_mode: str
    teaching_difficulty: str
    submit_type: str
    submit_count: int
    master_level: float | None = None
    mastery: float | None = None
    priority: float | None = None
    next_action: str | None = None
    state_sync_status: str
    step_feedback: str


class ExternalErrorAnalyzeRequest(BaseModel):
    student_id: int
    question_id: str
    student_answer: str
    correct_answer: str


class CreateBatchRequest(BaseModel):
    class_id: str
    teacher_id: str
    batch_date: str
    question_ids: list[str]


class BatchResponse(BaseModel):
    batch_id: str
    class_id: str
    teacher_id: str
    batch_date: str
    release_status: str
    question_count: int
    question_ids: list[str] = []
    question_details: list[dict] = []


class ReleasePartialRequest(BaseModel):
    question_ids: list[str]
