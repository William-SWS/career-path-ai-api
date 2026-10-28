from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # nullable=True explícito: é o que o banco tem hoje (o código sempre preenche). Tornar
    # estas colunas NOT NULL é uma migration à parte.
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=True
    )

    def __init__(self, token: str, expires_at: datetime):
        # Grante que expires_at tem timezone
        if expires_at.tzinfo is None:
            self.expires_at = expires_at.replace(tzinfo=UTC)
        else:
            self.expires_at = expires_at
        self.token = token
