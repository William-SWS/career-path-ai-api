from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.dependencies.rate_limit import (
    limit_forgot_password,
    limit_login,
    limit_login_form,
    limit_register,
    limit_reset_password,
)
from app.api.v1.dependencies.security import oauth2_scheme, verify_refresh_token, verify_token
from app.api.v1.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.user_services import UserService

router = APIRouter()


@router.post(
    "/register", response_model=MessageResponse, status_code=201, dependencies=[Depends(limit_register)]
)
async def create_account(
    user_data: RegisterRequest, user_service: UserService = Depends(get_user_service)
):
    """
    Cria um novo usuário no banco de dados.
    """
    return await user_service.create_user_account(user_data)


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(limit_login)])
async def login(login_schema: LoginRequest, user_service: UserService = Depends(get_user_service)):
    """
    Autentica usuários no sistema.
    """
    return await user_service.login(login_schema)


@router.post("/login-form", response_model=TokenResponse, dependencies=[Depends(limit_login_form)])
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
    logout_data: LogoutRequest | None = None,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(verify_token),
    user_service: UserService = Depends(get_user_service)
):
    """
    Faz logout adicionando o access token (e o refresh token, se enviado) à blacklist
    """
    refresh_token = logout_data.refresh_token if logout_data else None
    return await user_service.logout(token, current_user, refresh_token)


@router.post(
    "/forgot-password", response_model=MessageResponse, dependencies=[Depends(limit_forgot_password)]
)
async def forgot_password(request_data: ForgotPasswordRequest, background_tasks: BackgroundTasks, user_service: UserService = Depends(get_user_service)):
    return await user_service.forgot_user_password(request_data, background_tasks)


@router.post(
    "/reset-password", response_model=MessageResponse, dependencies=[Depends(limit_reset_password)]
)
async def reset_password(request_data: ResetPasswordRequest, user_service: UserService = Depends(get_user_service)):
    """
    Reseta a senha do usuário.
    """
    return await user_service.reset_user_password(request_data)
