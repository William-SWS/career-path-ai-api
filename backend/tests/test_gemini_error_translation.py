"""Falhas do provedor de IA viram exceções de domínio, sem detalhes do SDK."""
import asyncio
from types import SimpleNamespace

import google.generativeai as genai
import pytest
from google.api_core import exceptions as google_exceptions

from app.core.exceptions import ExternalServiceException, RateLimitException
from app.schemas.development_trail_schema import DevelopmentTrailRequest
from app.utils.development_trail_utils import generate_development_trail_with_gemini
from app.utils.interview_guide_utils import generate_interview_guide_with_gemini
from app.utils.resume_analysis_utils import analyze_with_gemini

SECRET = "projects/123/locations/us/apiKey=AIza-secret"

TRAIL_REQUEST = DevelopmentTrailRequest(
    name="Maria", skills=["Python"], professional_goal="Back-End"
)

GENERATORS = {
    "trail": lambda: generate_development_trail_with_gemini(TRAIL_REQUEST),
    "interview": lambda: generate_interview_guide_with_gemini("cv text", "job text"),
    "resume": lambda: analyze_with_gemini("cv text"),
}


class FakeResponse:
    def __init__(self, text, candidates):
        self.text = text
        self.candidates = [SimpleNamespace(finish_reason="STOP")] * candidates


def fake_model(*, raises=None, text='{"ok": true}', candidates=1):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            if raises:
                raise raises
            return FakeResponse(text, candidates)

    return FakeModel


@pytest.fixture(params=GENERATORS)
def generate(request, monkeypatch):
    def run(model):
        monkeypatch.setattr(genai, "GenerativeModel", model)
        return asyncio.run(GENERATORS[request.param]())

    return run


def test_returns_parsed_json_on_success(generate):
    assert generate(fake_model()) == {"ok": True}


def test_quota_exhausted_is_rate_limit(generate):
    with pytest.raises(RateLimitException) as exc_info:
        generate(fake_model(raises=google_exceptions.ResourceExhausted(SECRET)))

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "ai_quota_exceeded"
    assert SECRET not in exc_info.value.message


def test_provider_failure_is_external_service_error(generate):
    with pytest.raises(ExternalServiceException) as exc_info:
        generate(fake_model(raises=google_exceptions.ServiceUnavailable(SECRET)))

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "ai_provider_error"
    assert SECRET not in exc_info.value.message


@pytest.mark.parametrize(
    "model",
    [
        fake_model(text="this is not json at all"),
        fake_model(candidates=0),  # resposta bloqueada: sem candidatos
    ],
    ids=["unparsable-text", "no-candidates"],
)
def test_unusable_response_is_invalid_response_error(generate, model):
    with pytest.raises(ExternalServiceException) as exc_info:
        generate(model)

    assert exc_info.value.code == "ai_invalid_response"


def test_unexpected_programming_error_is_not_swallowed(generate):
    with pytest.raises(KeyError):
        generate(fake_model(raises=KeyError("bug")))
