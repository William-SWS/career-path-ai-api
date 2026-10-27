from fastapi import Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.config import settings
from app.core.security import is_token_blacklisted
from app.api.v1.dependencies.database import get_db
from app.utils.token_utils import decode_jwt_token
from jose import JWTError
from typing import Optional


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login-form")


async def verify_token(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    try:
        # Verifica se o token ta na blacklist
        if await is_token_blacklisted(token, db):
            raise HTTPException(
                status_code=401,
                detail="Token revoked"
            )
        
        payload = decode_jwt_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Não foi possível validar as credenciais",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token é inválido ou está expirado")
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Não foi possível validar as credenciais",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def verify_refresh_token(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Verifica o refresh token, permitindo tokens expirados (mas válidos)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token de refresh não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Verifica se o token está na blacklist
        if await is_token_blacklisted(token, db):
            raise HTTPException(
                status_code=401,
                detail="Token revogado"
            )
        
        # Decodifica o token mesmo se estiver expirado (para refresh)
        from jose import jwt
        from app.core.config import settings
        
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}  # Permite tokens expirados para refresh
            )
        except JWTError:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Não foi possível validar as credenciais",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token inválido ou está expirado")
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
