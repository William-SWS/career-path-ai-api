from fastapi import APIRouter, Depends

from app.api.v1.dependencies.security import verify_token
from app.api.v1.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.user_schema import (
    MessageResponse,
    UserDeleteRequest,
    UserGetResponse,
    UserUpdateRequest,
    UserUpdateResponse,
)
from app.services.user_services import UserService

router = APIRouter()


@router.patch("/me", response_model=UserUpdateResponse)
async def update_user_data(
    user_data: UserUpdateRequest,
    current_user: User = Depends(verify_token),
    user_service: UserService = Depends(get_user_service),
):
    """
    Atualiza os dados do usuário.
    """
    return await user_service.update_user(user_data, current_user)


@router.delete("/me/delete", response_model=MessageResponse)
async def delete(
    user_data: UserDeleteRequest,
    current_user: User = Depends(verify_token),
    user_service: UserService = Depends(get_user_service),
):
    """
    Deleta o usuário.
    """
    return await user_service.delete_user(user_data, current_user)


@router.get("/me", response_model=UserGetResponse)
async def get_user_data(
    current_user: User = Depends(verify_token),
    user_service: UserService = Depends(get_user_service),
):
    """
    Retorna os dados do usuário.
    """
    return await user_service.retrieve_user_data(current_user)
