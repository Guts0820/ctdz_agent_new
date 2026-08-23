from pydantic import BaseModel


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
