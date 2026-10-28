from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DevelopmentTrailStatus(str, Enum):
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class DevelopmentTrail(Base):
    __tablename__ = "development_trails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    development_trail = Column(JSON, nullable=False)
    status = Column(
        String(20),
        default=DevelopmentTrailStatus.IN_PROGRESS.value,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="development_trails")

    def __init__(
        self,
        user_id: int,
        development_trail: dict,
        created_at: datetime = None,
        status: DevelopmentTrailStatus = DevelopmentTrailStatus.IN_PROGRESS.value,
        updated_at: datetime = None
    ):
        self.user_id = user_id
        self.development_trail = development_trail
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
