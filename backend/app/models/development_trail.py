from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class DevelopmentTrailStatus(str, Enum):
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class DevelopmentTrail(Base):
    __tablename__ = "development_trails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    development_trail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default=DevelopmentTrailStatus.IN_PROGRESS.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="development_trails")

    def __init__(
        self,
        user_id: int,
        development_trail: dict,
        created_at: datetime | None = None,
        status: DevelopmentTrailStatus | str = DevelopmentTrailStatus.IN_PROGRESS.value,
        updated_at: datetime | None = None,
    ):
        self.user_id = user_id
        self.development_trail = development_trail
        self.status = status
        # Sem valor, a coluna usa o default (func.now()) em vez de gravar None.
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at
