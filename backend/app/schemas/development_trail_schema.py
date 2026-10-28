from pydantic import BaseModel, Field, StringConstraints, field_validator
from typing import Annotated, List, Optional, Dict, Any
from datetime import datetime
from ..models.development_trail import DevelopmentTrailStatus


class DevelopmentTrailRequest(BaseModel):
    # Limites de tamanho: estes textos vão para o prompt, então ficam curtos por custo e abuso.
    name: str = Field(..., min_length=1, max_length=100, example="Joao")
    age: Optional[int] = Field(None, ge=0, le=120, example=23)
    education: Optional[str] = Field(None, max_length=200, example="Graduação em andamento")
    current_area: Optional[str] = Field(None, max_length=200, example="Estudante de TI")
    experience_in_years: Optional[int] = Field(None, ge=0, le=80, example=1)
    skills: List[Annotated[str, StringConstraints(max_length=60)]] = Field(
        ..., max_length=30, example=["Python", "SQL", "Git"]
    )
    interested_technologies: Optional[List[Annotated[str, StringConstraints(max_length=60)]]] = Field(
        None, max_length=30, example=["Back-End", "Data Science"]
    )
    current_level: Optional[str] = Field(None, max_length=50, example="Intermediário")
    professional_goal: str = Field(..., min_length=1, max_length=200, example="Desenvolvimento Back-End")
    available_time_week: Optional[str] = Field(None, max_length=100, example="Até 15 horas semanais")
    goal_timeframe: Optional[str] = Field(None, max_length=100, example="Conseguir estágio em até 6 meses")
    additional_information: Optional[str] = Field(
        None, max_length=1000, example="Tenho interesse em DevOps e bancos de dados"
    )


class DevelopmentTrailResponse(BaseModel):
    id: int
    development_trail: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class DevelopmentTrailListResponse(BaseModel):
    development_trails: List[DevelopmentTrailResponse]
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