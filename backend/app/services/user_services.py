from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_password_reset_email
from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.security import (
    TokenType,
    add_token_to_blacklist,
    bcrypt_context,
    create_token,
    is_token_blacklisted,
)
from app.models.user import User
from app.repository.user_repository import UserRepository
from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.user_schema import (
    UserDeleteRequest,
    UserGetResponse,
    UserUpdateRequest,
    UserUpdateResponse,
)
from app.utils.token_utils import (
    get_token_subject,
    read_reset_password_token,
    reset_token_matches_password,
)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repository = UserRepository(db)

    async def create_user_account(self, user_data: RegisterRequest) -> MessageResponse:
        if await self.user_repository.email_exists(user_data.email):
            raise ConflictException("Esse email já está em uso", code="email_already_registered")

        crypted_password = bcrypt_context.hash(user_data.password)

        await self.user_repository.create(
            name=user_data.name,
            email=user_data.email,
            password_hash=crypted_password,
        )
        await self.db.commit()

        return MessageResponse(message="Usuário criado com sucesso")

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(email)

        if not user:
            # Gasta o mesmo tempo de hashing de uma conta real, para que o tempo
            # de resposta não revele quais e-mails estão cadastrados.
            bcrypt_context.dummy_verify()
            raise AuthenticationException("Credenciais inválidas", code="invalid_credentials")

        if not bcrypt_context.verify(password, user.password_hash):
            raise AuthenticationException("Credenciais inválidas", code="invalid_credentials")

        return user

    async def login(self, login_schema: LoginRequest) -> LoginResponse:
        user = await self.authenticate_user(login_schema.email, login_schema.password)

        access_token = create_token(user.id)
        refresh_token = create_token(user.id, TokenType.REFRESH)

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
            ),
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

    async def logout(
        self, access_token: str, current_user: User, refresh_token: str | None = None
    ) -> MessageResponse:
        """Revoga o access token e, se enviado, o refresh token, na mesma transação."""
        revoke_refresh = False

        if refresh_token:
            subject = get_token_subject(refresh_token, TokenType.REFRESH)
            # Inválido, expirado ou de outro tipo: não há sessão a revogar.
            if subject is not None:
                if subject != str(current_user.id):
                    raise ValidationException(
                        "O refresh token não pertence ao usuário autenticado",
                        code="refresh_token_mismatch",
                    )
                revoke_refresh = not await is_token_blacklisted(refresh_token, self.db)

        await add_token_to_blacklist(access_token, self.db)
        if revoke_refresh:
            await add_token_to_blacklist(refresh_token, self.db)
        await self.db.commit()

        return MessageResponse(message="Logout realizado com sucesso")

    async def update_user(
        self, user_data: UserUpdateRequest, current_user: User
    ) -> UserUpdateResponse:
        if not any([user_data.name, user_data.email]):
            raise ValidationException(
                "Pelo menos um campo deve ser fornecido", code="no_fields_to_update"
            )

        if user_data.email and user_data.email != current_user.email:
            if await self.user_repository.email_exists(user_data.email):
                raise ConflictException(
                    "Esse email já está em uso", code="email_already_registered"
                )

        updated_data = user_data.model_dump(exclude_unset=True, exclude_none=True)

        updated_user = await self.user_repository.update(current_user.id, **updated_data)
        await self.db.commit()
        await self.db.refresh(updated_user)

        return UserUpdateResponse(
            id=updated_user.id,
            name=updated_user.name,
            email=updated_user.email,
            updated_at=updated_user.updated_at,
        )

    async def delete_user(
        self, user_data: UserDeleteRequest, current_user: User
    ) -> MessageResponse:
        # 403 e não 401: a sessão é válida, só a confirmação falhou. Um 401 faria
        # o frontend tentar renovar o token e deslogar o usuário.
        if not bcrypt_context.verify(user_data.password, current_user.password_hash):
            raise PermissionDeniedException("Senha incorreta", code="invalid_password")

        await self.user_repository.delete(current_user.id)
        await self.db.commit()

        return MessageResponse(message="Usuário deletado com sucesso")

    async def retrieve_user_data(self, current_user: User) -> UserGetResponse:
        user = await self.user_repository.get_by_id(current_user.id)

        if not user:
            raise NotFoundException("Usuário não encontrado", code="user_not_found")

        return UserGetResponse(email=user.email, name=user.name, created_at=user.created_at)

    async def forgot_user_password(
        self, request_data: ForgotPasswordRequest, background_tasks
    ) -> MessageResponse:
        """
        Envia o e-mail de reset se a conta existir. A resposta é a mesma nos dois
        casos, para não revelar quais e-mails estão cadastrados.
        """
        user = await self.user_repository.get_by_email(request_data.email)
        if user:
            await send_password_reset_email(user, background_tasks)

        return MessageResponse(message="Se o email existir, enviaremos instruções de reset")

    async def reset_user_password(self, request_data: ResetPasswordRequest) -> MessageResponse:
        claims = read_reset_password_token(request_data.reset_token)
        if not claims:
            raise ValidationException("Token inválido ou expirado", code="invalid_reset_token")

        user = await self.user_repository.get_by_email(claims.email)
        if not user:
            raise NotFoundException("Usuário não encontrado", code="user_not_found")

        # O token só vale para a senha que existia quando ele foi emitido.
        if not reset_token_matches_password(claims, user.password_hash):
            raise ValidationException("Token inválido ou expirado", code="invalid_reset_token")

        hashed_password = bcrypt_context.hash(request_data.new_password)

        await self.user_repository.update_password(user.id, hashed_password)
        await self.db.commit()

        return MessageResponse(message="Senha resetada com sucesso")
