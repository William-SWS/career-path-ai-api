from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
from fastapi_mail import ConnectionConfig
from pathlib import Path

class Settings(BaseSettings):
    # hide_input_in_errors: um erro de validação nunca imprime o valor recebido
    # (ex.: uma SECRET_KEY curta) no log de inicialização.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    # App
    API_V1_STR: str = "/api/v1"
    APP_NAME: str = "Career-Path-AI"
    FRONTEND_HOST: str

    # Database Configuration
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def DATABASE_URI(self) -> str:
        return(
            "postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Security
    SECRET_KEY: str
    ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError(
                "SECRET_KEY deve ter pelo menos 32 caracteres. Gere uma com: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [self.FRONTEND_HOST.rstrip("/")]

    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True

    RESET_PASSWORD_TOKEN_EXPIRE_HOURS: int = 1

    # Gemini
    GEMINI_API_KEY: str


settings = Settings()

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates",
)