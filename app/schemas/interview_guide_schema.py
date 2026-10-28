from typing import Any

from pydantic import BaseModel, ConfigDict


class InterviewGuideResponse(BaseModel):
    id: int
    interview_guide: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class InterviewGuideListResponse(BaseModel):
    interview_guides: list[InterviewGuideResponse]
    total_count: int


class InterviewGuideDeleteResponse(BaseModel):
    message: str
    deleted_id: int
