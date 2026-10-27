"""Falhas do provedor de IA viram exceções de domínio, sem detalhes do SDK."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from app.core.exceptions import ExternalServiceException, RateLimitException
from app.llm.client import GeminiClient, GenerationParams
from app.llm.responses import parse_json_response

SECRET = "projects/123/locations/us/apiKey=AIza-secret"
PARAMS = GenerationParams(temperature=0.2, top_p=0.7, top_k=40, max_output_tokens=123)


class FakeModels:
    def __init__(self, response=None, error=None, delay=0):
        self.response = response
        self.error = error
        self.delay = delay
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.response


def response(text='{"ok": true}', finish_reason=types.FinishReason.STOP, candidates=True):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish_reason)] if candidates else [],
    )


def make_client(models, timeout=20):
    sdk = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiClient(api_key="k", model="test-model", timeout_seconds=timeout, client=sdk)


def generate(models, timeout=20):
    return asyncio.run(make_client(models, timeout).generate("prompt", PARAMS))


def test_returns_text_and_sends_model_prompt_and_config():
    models = FakeModels(response=response("  hello  "))

    assert generate(models) == "hello"

    call = models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == "prompt"
    assert call["config"].temperature == 0.2
    assert call["config"].top_p == 0.7
    assert call["config"].top_k == 40
    assert call["config"].max_output_tokens == 123


def test_quota_exhausted_is_rate_limit():
    models = FakeModels(error=errors.APIError(429, {"error": {"message": SECRET, "status": "RESOURCE_EXHAUSTED"}}))

    with pytest.raises(RateLimitException) as exc_info:
        generate(models)

    assert exc_info.value.code == "ai_quota_exceeded"
    assert SECRET not in str(exc_info.value.message)


@pytest.mark.parametrize("code", [400, 403, 500, 503])
def test_other_provider_errors_are_external_service_errors(code):
    models = FakeModels(error=errors.APIError(code, {"error": {"message": SECRET, "status": "X"}}))

    with pytest.raises(ExternalServiceException) as exc_info:
        generate(models)

    assert exc_info.value.code == "ai_provider_error"
    assert SECRET not in str(exc_info.value.message)


def test_http_timeout_is_ai_timeout():
    with pytest.raises(ExternalServiceException) as exc_info:
        generate(FakeModels(error=httpx.ReadTimeout(SECRET)))

    assert exc_info.value.code == "ai_timeout"


def test_hard_timeout_is_ai_timeout(monkeypatch):
    monkeypatch.setattr("app.llm.client._HARD_TIMEOUT_MARGIN_SECONDS", -20)

    with pytest.raises(ExternalServiceException) as exc_info:
        generate(FakeModels(response=response(), delay=1), timeout=20)

    assert exc_info.value.code == "ai_timeout"


def test_network_failure_is_provider_error():
    with pytest.raises(ExternalServiceException) as exc_info:
        generate(FakeModels(error=httpx.ConnectError(SECRET)))

    assert exc_info.value.code == "ai_provider_error"
    assert SECRET not in str(exc_info.value.message)


@pytest.mark.parametrize(
    "bad",
    [response(text=None), response(text="   "), response(text="", candidates=False)],
    ids=["none", "blank", "no-candidates"],
)
def test_empty_response_is_invalid_response(bad):
    with pytest.raises(ExternalServiceException) as exc_info:
        generate(FakeModels(response=bad))

    assert exc_info.value.code == "ai_invalid_response"


def test_truncated_response_is_still_returned():
    assert generate(FakeModels(response=response("{", types.FinishReason.MAX_TOKENS))) == "{"


def test_missing_api_key_is_unavailable():
    client = GeminiClient(api_key="", model="m", timeout_seconds=20)

    with pytest.raises(ExternalServiceException) as exc_info:
        asyncio.run(client.generate("p", PARAMS))

    assert exc_info.value.code == "ai_unavailable"


def test_unexpected_programming_error_is_not_swallowed():
    with pytest.raises(KeyError):
        generate(FakeModels(error=KeyError("bug")))


# ---------- parse_json_response ----------

def test_parse_json_response_returns_the_parsed_dict():
    assert parse_json_response(lambda t: {"a": 1}, "x") == {"a": 1}


@pytest.mark.parametrize("parsed", [{}, [], None, "text"], ids=repr)
def test_parse_json_response_rejects_unusable_results(parsed):
    with pytest.raises(ExternalServiceException) as exc_info:
        parse_json_response(lambda t: parsed, "x")

    assert exc_info.value.code == "ai_invalid_response"


def test_parse_json_response_converts_parser_failure():
    def parser(text):
        raise ValueError("boom")

    with pytest.raises(ExternalServiceException) as exc_info:
        parse_json_response(parser, "x")

    assert exc_info.value.code == "ai_invalid_response"
