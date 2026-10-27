"""Garante que tokens e detalhes de depuração não vazam (stdout, endpoints)."""
import asyncio
from types import SimpleNamespace

from fastapi import BackgroundTasks

from app.core.email import send_password_reset_email


def test_removed_debug_endpoints_are_not_exposed(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/check/models" not in paths
    assert "/api/v1/development-trail/test-prompt" not in paths


def test_password_reset_email_does_not_print_token(capsys):
    user = SimpleNamespace(email="user@example.com", name="User")

    asyncio.run(send_password_reset_email(user, BackgroundTasks()))

    assert capsys.readouterr().out == ""
