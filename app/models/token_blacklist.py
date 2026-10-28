from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class TokenBlacklist(Base):
    """Tokens revogados. Guarda só o `jti` (identificador do token), nunca o JWT."""

    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    jti: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    # Depois de expires_at o token já seria recusado pela expiração: a linha pode ser apagada.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __init__(self, jti: str, expires_at: datetime):
        # Garante que expires_at tem timezone
        if expires_at.tzinfo is None:
            self.expires_at = expires_at.replace(tzinfo=UTC)
        else:
            self.expires_at = expires_at
        self.jti = jti
