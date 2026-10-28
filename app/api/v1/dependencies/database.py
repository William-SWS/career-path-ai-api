from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import get_db, get_db_sync

SessionDep = Annotated[AsyncSession, Depends(get_db)]
SyncSessionDep = Annotated[Session, Depends(get_db_sync)]
