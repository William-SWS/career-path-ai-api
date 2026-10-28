from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class InterviewGuide(Base):
    __tablename__ = "interview_guide"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    interview_guide = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    user = relationship("User", back_populates="interview_guide")

    def __init__(self, user_id: int, interview_guide: dict, created_at: datetime):
        self.user_id = user_id
        self.interview_guide = interview_guide
        self.created_at = created_at
