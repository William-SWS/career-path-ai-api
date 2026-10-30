import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from app.core import email as email_module
from app.core.email import send_email


class FakeMail:
    """Falha nas primeiras `failures` chamadas e depois aceita o envio."""

    def __init__(self, failures: int = 0, error: Exception | None = None):
        self.failures = failures
        self.error = error or ConnectionError("smtp indisponível para user@example.com")
        self.calls = 0
        self.sent: list = []

    async def send_message(self, message, template_name):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        self.sent.append((message, template_name))


@pytest.fixture
def sleeps(monkeypatch):
    waited: list[float] = []

    async def fake_sleep(seconds):
        waited.append(seconds)

    monkeypatch.setattr(email_module, "asyncio", SimpleNamespace(sleep=fake_sleep))
    return waited


def make_mail(monkeypatch, fake):
    monkeypatch.setattr(email_module, "FastMail", lambda conf: fake)


def run_tasks(background_tasks: BackgroundTasks):
    asyncio.run(background_tasks())


def schedule(background_tasks: BackgroundTasks):
    send_email(
        recipients=["user@example.com"],
        subject="Reset",
        context={"name": "User"},
        template_name="password_reset.html",
        background_tasks=background_tasks,
    )


def test_send_email_only_schedules_and_does_not_touch_smtp(monkeypatch):
    fake = FakeMail()
    make_mail(monkeypatch, fake)
    tasks = BackgroundTasks()

    schedule(tasks)

    assert fake.calls == 0
    assert len(tasks.tasks) == 1


def test_delivers_on_first_attempt_without_waiting(monkeypatch, sleeps):
    fake = FakeMail()
    make_mail(monkeypatch, fake)
    tasks = BackgroundTasks()
    schedule(tasks)

    run_tasks(tasks)

    assert fake.calls == 1
    assert fake.sent[0][1] == "password_reset.html"
    assert sleeps == []


def test_retries_transient_failure_and_delivers(monkeypatch, sleeps, caplog):
    fake = FakeMail(failures=2)
    make_mail(monkeypatch, fake)
    tasks = BackgroundTasks()
    schedule(tasks)

    with caplog.at_level(logging.WARNING, logger="app"):
        run_tasks(tasks)

    assert fake.calls == 3
    assert len(fake.sent) == 1
    assert sleeps == [1, 3]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_gives_up_after_last_attempt_without_raising(monkeypatch, sleeps, caplog):
    fake = FakeMail(failures=99)
    make_mail(monkeypatch, fake)
    tasks = BackgroundTasks()
    schedule(tasks)

    with caplog.at_level(logging.WARNING, logger="app"):
        run_tasks(tasks)

    assert fake.calls == 3
    assert fake.sent == []
    assert sleeps == [1, 3]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "ConnectionError" in errors[0].getMessage()


def test_logs_never_contain_the_recipient(monkeypatch, sleeps, caplog):
    fake = FakeMail(failures=99)
    make_mail(monkeypatch, fake)
    tasks = BackgroundTasks()
    schedule(tasks)

    with caplog.at_level(logging.DEBUG, logger="app"):
        run_tasks(tasks)

    assert "user@example.com" not in caplog.text
