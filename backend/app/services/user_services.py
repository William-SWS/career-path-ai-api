from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.core.logging_config import logger
from app.core.security import bcrypt_context, create_token, add_token_to_blacklist
from app.core.email import send_password_reset_email
from app.utils.token_utils import verify_reset_password_token
from app.schemas.user_schema import (
    UserUpdateRequest,
    UserUpdateResponse,
    UserDeleteRequest,
    UserGetResponse
)
from app.schemas.auth_schema import (
    RegisterRequest,
    MessageResponse,
    TokenResponse,
    RefreshTokenResponse,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LoginResponse,
    UserResponse,
)
from datetime import timedelta
from app.repository.user_repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repository = UserRepository(db)

    async def create_user_account(
        self, user_data: RegisterRequest
    ) -> MessageResponse:
        try:
            if await self.user_repository.email_exists(user_data.email):
                raise HTTPException(status_code=400, detail="Esse email já está em uso")

            crypted_password = bcrypt_context.hash(user_data.password)

            await self.user_repository.create(
                name=user_data.name,
                email=user_data.email,
                password_hash=crypted_password,
            )

            return MessageResponse(message="Usuário criado com sucesso")

        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro interno ao criar usuário")
            raise HTTPException(
                status_code=500, detail="Erro interno ao criar usuário"
            )

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(email)

        if not user or not bcrypt_context.verify(password, user.password_hash):
            raise HTTPException(
                status_code=400,
                detail="Credenciais inválidas",
            )

        return user

    async def login(self, login_schema: LoginRequest) -> LoginResponse:
        user = await self.authenticate_user(login_schema.email, login_schema.password)

        access_token = create_token(user.id)
        refresh_token = create_token(user.id, token_duration=timedelta(days=7))

        return LoginResponse(
            data=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
            ),
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="Bearer",
            )
        )

    async def login_form(self, form_data: OAuth2PasswordRequestForm) -> TokenResponse:
        user = await self.authenticate_user(form_data.username, form_data.password)

        access_token = create_token(user.id)
        return TokenResponse(
                access_token=access_token,
                refresh_token="",
                token_type="Bearer",
            )

    async def use_refresh_token(self, user: User) -> RefreshTokenResponse:
        access_token = create_token(user.id)
        return RefreshTokenResponse(access_token=access_token, token_type="Bearer")

    async def logout(self, request: Request, current_user: User) -> MessageResponse:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token inválido")

        token = authorization.replace("Bearer ", "")

        # Note: add_token_to_blacklist precisa ser adaptado para usar repository
        await add_token_to_blacklist(token, self.db)

        return MessageResponse(message="Logout realizado com sucesso")

    async def update_user(
        self, user_data: UserUpdateRequest, current_user: User
    ) -> UserUpdateResponse:
        try:
            if not any([user_data.name, user_data.email]):
                raise HTTPException(
                    status_code=400, detail="Pelo menos um campo deve ser fornecido"
                )

            email_exists = await self.user_repository.get_by_email(user_data.email)
            if email_exists:
                raise HTTPException(
                    status_code=400,
                    detail="Erro ao atualizar o email"
                )
            
            updated_data = user_data.model_dump(exclude_unset=True, exclude_none=True)

            updated_user = await self.user_repository.update(
                current_user.id, **updated_data
            )

            return UserUpdateResponse(
                id=updated_user.id,
                name=updated_user.name,
                email=updated_user.email,
                updated_at=updated_user.updated_at,
            )
        except HTTPException:
            raise

    async def delete_user(
        self, user_data: UserDeleteRequest, current_user: User
    ) -> MessageResponse:
        try:
            if not bcrypt_context.verify(
                user_data.password, current_user.password_hash
            ):
                raise HTTPException(status_code=400, detail="Senha incorreta")

            await self.user_repository.delete(current_user.id)

            return MessageResponse(message="Usuário deletado com sucesso")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro interno no servidor")
            raise HTTPException(
                status_code=500, detail="Erro interno no servidor"
            )

    async def retrieve_user_data(self, current_user: User) -> UserGetResponse:
        try:
            user = await self.user_repository.get_by_id(current_user.id)

            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="Usuário não encontrado"
                )
            
            return UserGetResponse(
                email=user.email,
                name=user.name,
                created_at=user.created_at
            )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro interno no servidor")
            raise HTTPException(
                status_code=500, detail="Erro interno no servidor"
            )
    
    async def forgot_user_password(self, request_data: ForgotPasswordRequest, background_tasks) -> MessageResponse:
        """
        Recebe o email, busca usuário e envia email com token
        """
        try:
            user = await self.user_repository.get_by_email(request_data.email)
            if not user:
                raise HTTPException(
                    status_code=400,
                    detail="Erro ao gerar link para resetar senha"
                )
            
            await send_password_reset_email(user, background_tasks)

            return MessageResponse(message="Se o email existir, enviaremos instruções de reset")
        except HTTPException:
            raise

    async def reset_user_password(self, request_data: ResetPasswordRequest) -> MessageResponse:
        try:
            email = verify_reset_password_token(request_data.reset_token)
            if not email:
                raise HTTPException(status_code=400, detail="Token inválido ou expirado")

            user = await self.user_repository.get_by_email(email)
            if not user:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")

            hashed_password = bcrypt_context.hash(request_data.new_password)

            await self.user_repository.update_password(user.id, hashed_password)

            return MessageResponse(message="Senha resetada com sucesso")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Erro interno ao resetar senha")
            raise HTTPException(status_code=500, detail="Erro interno ao resetar senha")

