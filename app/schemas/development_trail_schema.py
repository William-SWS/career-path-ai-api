from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ..models.development_trail import DevelopmentTrailStatus


class DevelopmentTrailRequest(BaseModel):
    # Limites de tamanho: estes textos vão para o prompt, então ficam curtos por custo e abuso.
    name: str = Field(..., min_length=1, max_length=100, examples=["Joao"])
    age: int | None = Field(None, ge=0, le=120, examples=[23])
    education: str | None = Field(None, max_length=200, examples=["Graduação em andamento"])
    current_area: str | None = Field(None, max_length=200, examples=["Estudante de TI"])
    experience_in_years: int | None = Field(None, ge=0, le=80, examples=[1])
    skills: list[Annotated[str, StringConstraints(max_length=60)]] = Field(
        ..., max_length=30, examples=[["Python", "SQL", "Git"]]
    )
    interested_technologies: list[Annotated[str, StringConstraints(max_length=60)]] | None = Field(
        None, max_length=30, examples=[["Back-End", "Data Science"]]
    )
    current_level: str | None = Field(None, max_length=50, examples=["Intermediário"])
    professional_goal: str = Field(
        ..., min_length=1, max_length=200, examples=["Desenvolvimento Back-End"]
    )
    available_time_week: str | None = Field(
        None, max_length=100, examples=["Até 15 horas semanais"]
    )
    goal_timeframe: str | None = Field(
        None, max_length=100, examples=["Conseguir estágio em até 6 meses"]
    )
    additional_information: str | None = Field(
        None, max_length=1000, examples=["Tenho interesse em DevOps e bancos de dados"]
    )


class DevelopmentTrailResponse(BaseModel):
    id: int
    development_trail: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class DevelopmentTrailListResponse(BaseModel):
    development_trails: list[DevelopmentTrailResponse]
    total_count: int


class DevelopmentTrailUpdateRequest(BaseModel):
    status: DevelopmentTrailStatus

    @field_validator("status")
    def validate_status(cls, v):
        if v not in DevelopmentTrailStatus:
            raise ValueError(f"Status deve ser um dos seguintes: {list(DevelopmentTrailStatus)}")
        return v


class DevelopmentTrailDeleteResponse(BaseModel):
    message: str
    deleted_id: int
