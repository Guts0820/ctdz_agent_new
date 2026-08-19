from typing import Optional

from pydantic import BaseModel


class SubmitRequest(BaseModel):
    student_id: str
    question_id: Optional[str] = None
    image: Optional[str] = None
    original_question: Optional[str] = None
    student_write: Optional[str] = None
    grade: Optional[str] = "三年级"


class SubmitResponse(BaseModel):
    status: str
    data: dict


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


class ReleasePartialRequest(BaseModel):
    question_ids: list[str]
