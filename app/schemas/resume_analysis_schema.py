from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeAnalysisResponse(BaseModel):
    id: int
    original_filename: str
    analysis_result: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeAnalysisListResponse(BaseModel):
    analyses: list[ResumeAnalysisResponse]
    total_count: int


class ResumeAnalysisDeleteResponse(BaseModel):
    message: str
    deleted_id: int
