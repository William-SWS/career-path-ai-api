"""Garante que detalhes internos (exceções, tokens) não chegam ao cliente nem ao stdout."""
import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.core.email import send_password_reset_email
from app.schemas.auth_schema import RegisterRequest
from app.services.development_trail_services import DevelopmentTrailService
from app.services.user_services import UserService
from app.utils.pdf_utils import check_pdf

SECRET = "postgres://user:s3cr3t@db/internal"


class _ExplodingRepository:
    def __getattr__(self, name):
        async def boom(*args, **kwargs):
            raise RuntimeError(SECRET)

        return boom


def _pdf_upload(content: bytes, filename: str = "cv.pdf") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def test_removed_debug_endpoints_are_not_exposed(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/check/models" not in paths
    assert "/api/v1/development-trail/test-prompt" not in paths


def test_password_reset_email_does_not_print_token(capsys):
    user = SimpleNamespace(email="user@example.com", name="User")

    asyncio.run(send_password_reset_email(user, BackgroundTasks()))

    assert capsys.readouterr().out == ""


def test_service_hides_unexpected_error_details():
    service = DevelopmentTrailService(db=None)
    service.development_trail_repository = _ExplodingRepository()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.get_development_trail_by_id_service(1, SimpleNamespace(id=1))
        )

    assert exc_info.value.status_code == 500
    assert SECRET not in str(exc_info.value.detail)


def test_user_service_hides_unexpected_error_details():
    service = UserService(db=None)
    service.user_repository = _ExplodingRepository()
    data = RegisterRequest(name="Maria Silva", email="m@example.com", password="Abcdef1!")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.create_user_account(data))

    assert exc_info.value.status_code == 500
    assert SECRET not in str(exc_info.value.detail)


def test_pdf_empty_file_is_client_error_with_clear_message():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(check_pdf(_pdf_upload(b"")))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "O arquivo está vazio"


def test_pdf_corrupted_file_returns_generic_server_error():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(check_pdf(_pdf_upload(b"not really a pdf")))

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Erro interno ao checar o PDF"
