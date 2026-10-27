from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest, 
    TokenResponse, 
    MessageResponse, 
    RefreshTokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LoginResponse,
)
from app.api.v1.dependencies.security import oauth2_scheme, verify_token, verify_refresh_token
from app.models.user import User
from app.services.user_services import UserService
from app.api.v1.dependencies.services import get_user_service


router = APIRouter()


@router.post("/register", response_model=MessageResponse, status_code=201)
async def create_account(
    user_data: RegisterRequest, user_service: UserService = Depends(get_user_service)
):
    """
    Cria um novo usuário no banco de dados.
    """
    return await user_service.create_user_account(user_data)


@router.post("/login", response_model=LoginResponse)
async def login(login_schema: LoginRequest, user_service: UserService = Depends(get_user_service)):
    """
    Autentica usuários no sistema.
    """
    return await user_service.login(login_schema)


@router.post("/login-form", response_model=TokenResponse)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), user_service: UserService = Depends(get_user_service)):
    return await user_service.login_form(form_data)


@router.post("/refresh", response_model=RefreshTokenResponse)
async def use_refresh_token(
    user: User = Depends(verify_refresh_token),
    user_service: UserService = Depends(get_user_service)
):
    """
    Rota para gerar novo access token usando refresh token
    """
    return await user_service.use_refresh_token(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(verify_token),
    user_service: UserService = Depends(get_user_service)
):
    """
    Faz logout do usuário adicionando o token à blacklist
    """
    return await user_service.logout(token)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request_data: ForgotPasswordRequest, background_tasks: BackgroundTasks, user_service: UserService = Depends(get_user_service)):
    return await user_service.forgot_user_password(request_data, background_tasks)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request_data: ResetPasswordRequest, user_service: UserService = Depends(get_user_service)):
    """
    Reseta a senha do usuário.
    """
    return await user_service.reset_user_password(request_data)
