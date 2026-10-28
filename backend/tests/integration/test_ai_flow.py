"""Geração com IA ponta a ponta: HTTP → serviço → Postgres real, com o LLM trocado por FakeLLM."""
import json

import pytest

from app.llm.client import get_llm_client
from app.main import app
from app.schemas.ai_outputs import DevelopmentTrailOutput
from tests.fakes import FakeLLM, sample_output
from tests.integration.conftest import API, bearer

pytestmark = pytest.mark.integration

TRAIL = {"name": "Ana", "skills": ["Python"], "professional_goal": "Back-End"}


def use_llm(llm):
    app.dependency_overrides[get_llm_client] = lambda: llm


def test_generated_trail_is_persisted_and_listed(http, session_tokens):
    use_llm(FakeLLM(json.dumps(sample_output(DevelopmentTrailOutput))))
    headers = bearer(session_tokens["access_token"])

    created = http.post(f"{API}/development-trail/", json=TRAIL, headers=headers)

    assert created.status_code == 200
    listed = http.get(f"{API}/development-trail/", headers=headers).json()
    assert listed["total_count"] == 1
    assert listed["development_trails"][0]["development_trail"] == sample_output(DevelopmentTrailOutput)


def test_invalid_model_output_returns_502_and_saves_nothing(http, session_tokens):
    use_llm(FakeLLM("not json"))
    headers = bearer(session_tokens["access_token"])

    response = http.post(f"{API}/development-trail/", json=TRAIL, headers=headers)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai_invalid_response"
    assert http.get(f"{API}/development-trail/", headers=headers).json()["total_count"] == 0
