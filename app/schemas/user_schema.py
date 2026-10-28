import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.base_schema import BaseMessageResponse


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    name: str | None = None

    def has_at_least_one_field(self):
        return any([self.name is not None, self.email is not None])

    @field_validator("name")
    def validate_name(cls, name):
        if name is None:
            return name  # Não valida se não for enviado

        name = name.strip()

        if not name:
            raise ValueError("O nome não pode estar vazio.")

        pattern = r"^[A-Za-zÀ-ÿ ]+$"
        if not re.match(pattern, name):
            raise ValueError("O nome deve conter apenas letras e espaços.")

        if len(name.split()) < 2:
            raise ValueError("Informe nome e sobrenome.")

        return name


class UserUpdateResponse(BaseModel):
    email: EmailStr
    name: str
    updated_at: datetime


class UserDeleteRequest(BaseModel):
    password: str


class UserGetResponse(BaseModel):
    email: EmailStr
    name: str
    created_at: datetime


class MessageResponse(BaseMessageResponse):
    pass
