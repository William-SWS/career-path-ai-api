from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from typing import Optional
from app.repository.base_repository import BaseRepository
from datetime import datetime, timezone


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Busca o usuário por email
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def email_exists(self, email: str) -> bool:
        """
        Verifica se email já existe
        """
        user = await self.get_by_email(email)
        return user is not None
    
    async def update_password(self, user_id: int, hashed_password: str) -> Optional[User]:
        """
        Atualiza apenas a senha do usuário
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.password_hash = hashed_password
        user.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        return user
