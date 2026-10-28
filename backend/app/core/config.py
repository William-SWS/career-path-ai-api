from limits import parse as parse_limit
from pydantic import Field, field_validator
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
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # Mínimo de 20 s: o SDK responde um 500 sem causa clara a timeouts muito baixos
    # (googleapis/python-genai#1330).
    GEMINI_TIMEOUT_SECONDS: int = Field(default=90, ge=20, le=300)
    # 0 desliga o raciocínio, -1 deixa o modelo decidir. Nem todo modelo aceita 0 (ex.: 2.5-pro).
    GEMINI_THINKING_BUDGET: int = Field(default=0, ge=-1, le=24576)
    # Tentativas por geração (1 = sem retry) para erros transitórios do provedor.
    GEMINI_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=5)

    # Rate limiting. Sem REDIS_URL o contador fica na memória do processo (só serve para
    # desenvolvimento: não é compartilhado entre workers e zera a cada restart).
    REDIS_URL: str = ""
    # Quantos proxies de confiança estão na frente da API. Com 0 usa-se o IP da conexão;
    # X-Forwarded-For só é lido quando isso é configurado, porque o cliente pode forjá-lo.
    TRUSTED_PROXY_COUNT: int = Field(default=0, ge=0, le=5)
    # Formato da biblioteca `limits`: "<n>/<minute|hour|day>".
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_FORGOT_PASSWORD: str = "3/hour"
    RATE_LIMIT_RESET_PASSWORD: str = "10/hour"
    RATE_LIMIT_AI_USER_HOURLY: str = "10/hour"
    RATE_LIMIT_AI_USER_BURST: str = "3/minute"
    RATE_LIMIT_AI_GLOBAL: str = "20/minute"

    @field_validator(
        "RATE_LIMIT_LOGIN", "RATE_LIMIT_REGISTER", "RATE_LIMIT_FORGOT_PASSWORD",
        "RATE_LIMIT_RESET_PASSWORD", "RATE_LIMIT_AI_USER_HOURLY", "RATE_LIMIT_AI_USER_BURST",
        "RATE_LIMIT_AI_GLOBAL",
    )
    @classmethod
    def valid_rate_limit(cls, value: str) -> str:
        try:
            valid = parse_limit(value).amount >= 1
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('use o formato "<n>/<minute|hour|day>", por exemplo "5/minute"')
        return value


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