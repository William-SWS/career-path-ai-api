import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.base_schema import BaseMessageResponse

# O bcrypt só usa os primeiros 72 bytes: o que vier depois seria ignorado em silêncio.
BCRYPT_MAX_PASSWORD_BYTES = 72


def validate_new_password(pwd: str) -> str:
    """Regras de senha para cadastro e reset (o login não usa: não pode trancar quem já tem conta)."""
    erros = []

    if len(pwd) < 8:
        erros.append("no mínimo 8 caracteres")
    if not any(c.isupper() for c in pwd):
        erros.append("uma letra maiúscula")
    if not any(c.islower() for c in pwd):
        erros.append("uma letra minúscula")
    if not any(c.isdigit() for c in pwd):
        erros.append("um número")

    if erros:
        raise ValueError("A senha deve conter " + ", ".join(erros) + ".")

    if len(pwd.encode()) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"A senha deve ter no máximo {BCRYPT_MAX_PASSWORD_BYTES} bytes "
            "(caracteres acentuados ocupam mais de um byte)."
        )

    return pwd


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8, max_length=100)

    @field_validator("name")
    def validate_name(cls, name: str):
        name = name.strip()

        if not name:
            raise ValueError("O nome não pode estar vazio.")

        # Permitir letras + espaços + acentos
        # Bloqueia números e símbolos
        pattern = r"^[A-Za-zÀ-ÿ ]+$"
        if not re.match(pattern, name):
            raise ValueError("O nome deve conter apenas letras e espaços.")

        if len(name.split()) < 2:
            raise ValueError("Informe nome e sobrenome.")

        return name

    @field_validator("password")
    def validate_password(cls, pwd):
        return validate_new_password(pwd)

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    data: UserResponse
    tokens: TokenResponse


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    def validate_password(cls, pwd):
        return validate_new_password(pwd)

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseMessageResponse):
    pass
