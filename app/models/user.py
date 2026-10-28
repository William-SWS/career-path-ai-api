from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.development_trail import DevelopmentTrail
    from app.models.interview_guide import InterviewGuide
    from app.models.resume_analysis import ResumeAnalysis


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("id", Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("name", String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        "email", String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column("password_hash", String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    resume_analyses: Mapped[list["ResumeAnalysis"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    development_trails: Mapped[list["DevelopmentTrail"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    interview_guide: Mapped[list["InterviewGuide"]] = relationship(
        back_populates="user", cascade="all, delete"
    )

    def __init__(self, name: str, email: str, password_hash: str):
        self.name = name
        self.email = email
        self.password_hash = password_hash
