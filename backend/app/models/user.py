from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    name = Column("name", String(255), nullable=False)
    email = Column("email", String(255), unique=True, nullable=False, index=True)
    password_hash = Column("password_hash", String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    resume_analyses = relationship("ResumeAnalysis", back_populates="user", cascade="all, delete")
    development_trails = relationship("DevelopmentTrail", back_populates="user", cascade="all, delete")
    interview_guide = relationship("InterviewGuide", back_populates="user", cascade="all, delete")

    def __init__(self, name: str, email: str, password_hash: str):
        self.name = name
        self.email = email
        self.password_hash = password_hash
