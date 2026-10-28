from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    original_filename = Column(String(255), nullable=False)
    analysis_result = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    user = relationship("User", back_populates="resume_analyses")

    def __init__(
        self,
        user_id: int,
        original_filename: str,
        analysis_result: dict,
        created_at: datetime,
    ):
        self.user_id = user_id
        self.original_filename = original_filename
        self.analysis_result = analysis_result
        self.created_at = created_at
