from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)

    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())

    def __init__(self, token: str, expires_at: datetime):
        # Grante que expires_at tem timezone
        if expires_at.tzinfo is None:
            self.expires_at = expires_at.replace(tzinfo=UTC)
        else:
            self.expires_at = expires_at
        self.token = token
