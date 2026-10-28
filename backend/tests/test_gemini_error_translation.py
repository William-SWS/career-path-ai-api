"""Falhas do provedor de IA viram exceções de domínio, sem detalhes do SDK."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from app.core.exceptions import ExternalServiceException, RateLimitException
from app.llm.client import GeminiClient, GenerationParams
from app.llm.prompts import Prompt
from pydantic import BaseModel

from app.llm.responses import parse_structured_response

SECRET = "projects/123/locations/us/apiKey=AIza-secret"
PROMPT = Prompt(system="SYSTEM-RULES", user="prompt")
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
        usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, thoughts_token_count=0
        ),
        candidates=[SimpleNamespace(finish_reason=finish_reason)] if candidates else [],
    )


class Sleeper:
    """Substitui asyncio.sleep: o teste não espera e vê quais pausas o backoff pediu."""

    def __init__(self):
        self.delays = []

    async def __call__(self, delay):
        self.delays.append(delay)


def make_client(models, timeout=20, sleeper=None, **kwargs):
    sdk = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiClient(
        api_key="k", model="test-model", timeout_seconds=timeout, client=sdk,
        sleep=sleeper or Sleeper(), **kwargs,
    )


def generate(models, timeout=20):
    return asyncio.run(make_client(models, timeout).generate(PROMPT, PARAMS))


def test_returns_text_and_sends_model_prompt_and_config():
    models = FakeModels(response=response("  hello  "))

    assert generate(models) == "hello"

    call = models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == "prompt"
    assert call["config"].system_instruction == "SYSTEM-RULES"
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
        asyncio.run(client.generate(PROMPT, PARAMS))

    assert exc_info.value.code == "ai_unavailable"


def test_unexpected_programming_error_is_not_swallowed():
    with pytest.raises(KeyError):
        generate(FakeModels(error=KeyError("bug")))


def test_structured_request_sends_schema_and_json_mime_type():
    class Out(BaseModel):
        a: int

    models = FakeModels(response=response('{"a": 1}'))
    asyncio.run(make_client(models).generate(PROMPT, PARAMS, response_schema=Out))

    config = models.calls[0]["config"]
    assert config.response_schema is Out
    assert config.response_mime_type == "application/json"


def test_empty_system_instruction_is_not_sent():
    models = FakeModels(response=response())
    asyncio.run(make_client(models).generate(Prompt(system="", user="u"), PARAMS))

    assert models.calls[0]["config"].system_instruction is None


def test_plain_request_has_no_schema():
    models = FakeModels(response=response())
    generate(models)

    assert models.calls[0]["config"].response_schema is None


@pytest.mark.parametrize("budget", [0, 1024, -1])
def test_thinking_budget_reaches_the_sdk(budget):
    models = FakeModels(response=response())
    asyncio.run(make_client(models, thinking_budget=budget).generate(PROMPT, PARAMS))

    assert models.calls[0]["config"].thinking_config.thinking_budget == budget


# ---------- retry ----------

def api_error(code):
    return errors.APIError(code, {"error": {"message": "m", "status": "S"}})


class ScriptedModels(FakeModels):
    """Falha com cada erro da lista, na ordem, e depois responde."""

    def __init__(self, failures, response_):
        super().__init__(response=response_)
        self.failures = list(failures)

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            raise self.failures.pop(0)
        return self.response


@pytest.mark.parametrize("failure", [api_error(503), api_error(500), api_error(504), httpx.ConnectError("x")],
                         ids=["503", "500", "504", "connect"])
def test_transient_failure_is_retried_and_then_succeeds(failure):
    models = ScriptedModels([failure], response("ok"))
    sleeper = Sleeper()

    assert asyncio.run(make_client(models, sleeper=sleeper).generate(PROMPT, PARAMS)) == "ok"

    assert len(models.calls) == 2
    assert len(sleeper.delays) == 1


def test_backoff_grows_exponentially_with_jitter():
    models = ScriptedModels([api_error(503), api_error(503)], response("ok"))
    sleeper = Sleeper()

    asyncio.run(make_client(models, sleeper=sleeper, max_attempts=3, backoff_base_seconds=2.0).generate(PROMPT, PARAMS))

    first, second = sleeper.delays
    assert 1.0 <= first <= 2.0      # 2s * [0.5, 1]
    assert 2.0 <= second <= 4.0     # 4s * [0.5, 1]


def test_gives_up_after_max_attempts_and_reports_provider_error():
    models = ScriptedModels([api_error(503)] * 5, response("never"))

    with pytest.raises(ExternalServiceException) as exc_info:
        asyncio.run(make_client(models, max_attempts=3).generate(PROMPT, PARAMS))

    assert exc_info.value.code == "ai_provider_error"
    assert len(models.calls) == 3


def test_max_attempts_one_disables_retry():
    models = ScriptedModels([api_error(503)], response("never"))

    with pytest.raises(ExternalServiceException):
        asyncio.run(make_client(models, max_attempts=1).generate(PROMPT, PARAMS))

    assert len(models.calls) == 1


@pytest.mark.parametrize("failure", [api_error(429), api_error(400), api_error(403), httpx.ReadTimeout("x")],
                         ids=["quota", "400", "403", "timeout"])
def test_non_transient_failures_are_not_retried(failure):
    models = ScriptedModels([failure], response("never"))

    with pytest.raises((ExternalServiceException, RateLimitException)):
        asyncio.run(make_client(models).generate(PROMPT, PARAMS))

    assert len(models.calls) == 1


def test_retries_never_extend_past_the_overall_deadline(monkeypatch):
    monkeypatch.setattr("app.llm.client._HARD_TIMEOUT_MARGIN_SECONDS", -20)  # teto de 0s
    models = ScriptedModels([api_error(503)], response("never"))

    async def slow_sleep(delay):
        await asyncio.sleep(1)

    with pytest.raises(ExternalServiceException) as exc_info:
        asyncio.run(make_client(models, timeout=20, sleeper=slow_sleep).generate(PROMPT, PARAMS))

    assert exc_info.value.code == "ai_timeout"


def test_usage_is_logged_without_prompt_or_response_content(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="app"):
        generate(FakeModels(response=response("SECRET-ANSWER")))

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "prompt_tokens=10" in logged and "attempts=1" in logged
    assert "SECRET-ANSWER" not in logged and "prompt'" not in logged


# ---------- parse_structured_response ----------

class Item(BaseModel):
    name: str
    tags: list[str]


def test_parse_structured_response_returns_the_validated_model():
    assert parse_structured_response(Item, '{"name": "a", "tags": ["x"]}') == Item(name="a", tags=["x"])


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[]", "null", "{}", '{"name": "a"}', '{"name": 1, "tags": []}', '{"name": "a", "tags": ["x"]'],
    ids=repr,
)
def test_parse_structured_response_rejects_anything_outside_the_contract(text):
    with pytest.raises(ExternalServiceException) as exc_info:
        parse_structured_response(Item, text)

    assert exc_info.value.code == "ai_invalid_response"


def test_parse_structured_response_does_not_leak_model_content_in_the_message():
    with pytest.raises(ExternalServiceException) as exc_info:
        parse_structured_response(Item, '{"name": "' + SECRET + '"}')

    assert SECRET not in exc_info.value.message
