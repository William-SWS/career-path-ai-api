"""Regras dos serviços de IA: repositórios em memória e LLM substituído."""
import asyncio
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.core.exceptions import ExternalServiceException, NotFoundException, RateLimitException
from app.schemas.development_trail_schema import (
    DevelopmentTrailRequest,
    DevelopmentTrailUpdateRequest,
)
from app.schemas.ai_outputs import DevelopmentTrailOutput, InterviewGuideOutput, ResumeAnalysisOutput
from tests.fakes import FakeLLM, FakeSession, sample_output
from app.services import interview_guide_services, resume_analysis_services
from app.services.development_trail_services import DevelopmentTrailService
from app.services.interview_guide_services import InterviewGuideService
from app.services.resume_analysis_services import ResumeAnalysisService

USER = SimpleNamespace(id=1)
OTHER_USER_ID = 2
NOW = datetime.now(timezone.utc)


class FakeRepository:
    """Guarda registros em memória; só devolve os do dono, como o repositório real."""

    def __init__(self, *records):
        self.records = {r.id: r for r in records}
        self.created = []
        self.deleted_ids = []

    async def create(self, **fields):
        record = SimpleNamespace(**{"id": len(self.records) + 1, "updated_at": NOW, **fields})
        self.records[record.id] = record
        self.created.append(record)
        return record

    async def _owned(self, record_id, user_id):
        record = self.records.get(record_id)
        return record if record and record.user_id == user_id else None

    async def get_by_id_and_user_id(self, user_id, **ids):
        (record_id,) = ids.values()
        return await self._owned(record_id, user_id)

    async def get_by_user_id(self, user_id, skip, limit):
        owned = [r for r in self.records.values() if r.user_id == user_id]
        return owned[skip : skip + limit], len(owned)

    async def update_status(self, development_trail_id, status):
        record = self.records[development_trail_id]
        record.status = status
        return record

    async def delete(self, record_id):
        self.deleted_ids.append(record_id)


def run(coro):
    return asyncio.run(coro)


def make_service(cls, repository_attr, *records, llm=None):
    service = cls(db=FakeSession(), llm=llm or FakeLLM())
    repository = FakeRepository(*records)
    setattr(service, repository_attr, repository)
    return service, repository


def commits(service) -> int:
    return service.db.commits


def stub_pdf(monkeypatch, module, text="cv text"):
    async def fake_check_pdf(file):
        return text

    monkeypatch.setattr(module, "check_pdf", fake_check_pdf)


def trail_record(id=1, user_id=USER.id):
    return SimpleNamespace(
        id=id, user_id=user_id, development_trail={"phases": []},
        status="In Progress", created_at=NOW, updated_at=NOW,
    )


def guide_record(id=1, user_id=USER.id, content={"preparation_overview": "x"}):
    return SimpleNamespace(id=id, user_id=user_id, interview_guide=content, created_at=NOW)


def analysis_record(id=1, user_id=USER.id):
    return SimpleNamespace(
        id=id, user_id=user_id, original_filename="cv.pdf",
        analysis_result={"professional_summary": "x"}, created_at=NOW,
    )


def pdf_upload():
    return UploadFile(file=io.BytesIO(b"%PDF"), filename="cv.pdf")


TRAIL_REQUEST = DevelopmentTrailRequest(name="Maria", skills=["Python"], professional_goal="Back-End")


# ---------- geração: o resultado da IA só é salvo se for utilizável

UNUSABLE_AI_TEXTS = [
    "{}", "[]", "null", '"just text"', "no json at all", "",
    '{"user_profile_summary": {"current_profile": "x"}}',  # fora do contrato
    '```json\n{}\n```',  # markdown não é consertado
]


@pytest.mark.parametrize("bad_text", UNUSABLE_AI_TEXTS, ids=repr)
def test_trail_with_unusable_ai_result_is_not_saved(bad_text):
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository", llm=FakeLLM(bad_text))

    with pytest.raises(ExternalServiceException) as exc_info:
        run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert exc_info.value.code == "ai_invalid_response"
    assert repo.created == []
    assert commits(service) == 0


def test_trail_is_saved_for_the_requesting_user_and_the_prompt_reaches_the_model():
    llm = FakeLLM(json.dumps(sample_output(DevelopmentTrailOutput)))
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository", llm=llm)

    response = run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert repo.created[0].user_id == USER.id
    assert response.development_trail == sample_output(DevelopmentTrailOutput)
    assert llm.calls[0][2] is DevelopmentTrailOutput  # o schema vai ao provedor
    assert response.status == "In Progress"
    assert "Back-End" in llm.calls[0][0].user  # o objetivo do usuário foi para a mensagem
    assert commits(service) == 1


@pytest.mark.parametrize("error", [RateLimitException("slow down"), ExternalServiceException("down")])
def test_provider_errors_propagate_and_nothing_is_saved(error):
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository", llm=FakeLLM(error=error))

    with pytest.raises(type(error)):
        run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert repo.created == []
    assert commits(service) == 0


def test_interview_guide_with_unusable_ai_result_is_not_saved(monkeypatch):
    service, repo = make_service(InterviewGuideService, "interview_guide_repository", llm=FakeLLM("{}"))
    stub_pdf(monkeypatch, interview_guide_services)

    with pytest.raises(ExternalServiceException):
        run(service.generate_interview_guide_service(pdf_upload(), "job", USER))

    assert repo.created == []


def test_interview_guide_is_saved_and_receives_resume_and_job(monkeypatch):
    llm = FakeLLM(json.dumps(sample_output(InterviewGuideOutput)))
    service, repo = make_service(InterviewGuideService, "interview_guide_repository", llm=llm)
    stub_pdf(monkeypatch, interview_guide_services, text="RESUME-TEXT")

    response = run(service.generate_interview_guide_service(pdf_upload(), "JOB-TEXT", USER))

    assert response.interview_guide == sample_output(InterviewGuideOutput)
    assert len(repo.created) == 1
    assert "RESUME-TEXT" in llm.calls[0][0].user and "JOB-TEXT" in llm.calls[0][0].user


def test_resume_analysis_with_unusable_ai_result_is_not_saved(monkeypatch):
    service, repo = make_service(ResumeAnalysisService, "resume_analysis_repository", llm=FakeLLM("null"))
    stub_pdf(monkeypatch, resume_analysis_services)

    with pytest.raises(ExternalServiceException):
        run(service.analyze_resume_service(pdf_upload(), USER))

    assert repo.created == []


def test_resume_analysis_is_saved_and_receives_the_resume_text(monkeypatch):
    llm = FakeLLM(json.dumps(sample_output(ResumeAnalysisOutput)))
    service, repo = make_service(ResumeAnalysisService, "resume_analysis_repository", llm=llm)
    stub_pdf(monkeypatch, resume_analysis_services, text="RESUME-TEXT")

    response = run(service.analyze_resume_service(pdf_upload(), USER))

    assert response.analysis_result == sample_output(ResumeAnalysisOutput)
    assert "RESUME-TEXT" in llm.calls[0][0].user


# ---------- recursos de outro usuário ou inexistentes: sempre 404

CASES = [
    (DevelopmentTrailService, "development_trail_repository", trail_record,
     "get_development_trail_by_id_service", "development_trail_not_found"),
    (DevelopmentTrailService, "development_trail_repository", trail_record,
     "delete_development_trail_service", "development_trail_not_found"),
    (InterviewGuideService, "interview_guide_repository", guide_record,
     "get_interview_guide_by_id_service", "interview_guide_not_found"),
    (InterviewGuideService, "interview_guide_repository", guide_record,
     "delete_interview_guide_service", "interview_guide_not_found"),
    (ResumeAnalysisService, "resume_analysis_repository", analysis_record,
     "get_resume_analysis_by_id_service", "resume_analysis_not_found"),
    (ResumeAnalysisService, "resume_analysis_repository", analysis_record,
     "delete_resume_analysis_service", "resume_analysis_not_found"),
]


@pytest.mark.parametrize("cls, repo_attr, make_record, method, code", CASES,
                         ids=[f"{c[0].__name__}.{c[3]}" for c in CASES])
@pytest.mark.parametrize("owner_id", [None, OTHER_USER_ID], ids=["missing", "other-users"])
def test_unknown_or_foreign_resource_is_not_found(cls, repo_attr, make_record, method, code, owner_id):
    records = [make_record(id=1, user_id=owner_id)] if owner_id else []
    service, repo = make_service(cls, repo_attr, *records)

    with pytest.raises(NotFoundException) as exc_info:
        run(getattr(service, method)(1, USER))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == code
    assert repo.deleted_ids == []


def test_delete_removes_own_resource():
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository", trail_record())

    response = run(service.delete_development_trail_service(1, USER))

    assert response.deleted_id == 1
    assert repo.deleted_ids == [1]


def test_update_trail_status():
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository", trail_record())

    response = run(service.update_development_trail_status_service(
        1, DevelopmentTrailUpdateRequest(status="Completed"), USER))

    assert response.status == "Completed"


def test_update_status_of_foreign_trail_is_not_found():
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository", trail_record(user_id=OTHER_USER_ID))

    with pytest.raises(NotFoundException):
        run(service.update_development_trail_status_service(
            1, DevelopmentTrailUpdateRequest(status="Completed"), USER))


# ---------- listagem vazia não é erro

def test_empty_trail_list_is_a_valid_empty_response():
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository")

    response = run(service.get_development_trail_service(USER, skip=0, limit=10))

    assert response.development_trails == []
    assert response.total_count == 0


def test_interview_guide_without_content_is_returned_as_empty_object():
    service, _ = make_service(InterviewGuideService, "interview_guide_repository", guide_record(content=None))

    assert run(service.get_interview_guide_by_id_service(1, USER)).interview_guide == {}


# ---------- fronteira transacional: um commit por escrita, nenhum por leitura ou falha

def test_writes_commit_once_and_reads_never_commit():
    trail, _ = make_service(DevelopmentTrailService, "development_trail_repository", trail_record())
    guide, _ = make_service(InterviewGuideService, "interview_guide_repository", guide_record())
    analysis, _ = make_service(ResumeAnalysisService, "resume_analysis_repository", analysis_record())

    run(trail.get_development_trail_service(USER, 0, 10))
    run(trail.get_development_trail_by_id_service(1, USER))
    run(guide.get_interview_guide_service(USER, 0, 10))
    run(guide.get_interview_guide_by_id_service(1, USER))
    run(analysis.get_resume_analysis_service(USER, 0, 10))
    run(analysis.get_resume_analysis_by_id_service(1, USER))
    assert [commits(s) for s in (trail, guide, analysis)] == [0, 0, 0]

    run(trail.update_development_trail_status_service(1, DevelopmentTrailUpdateRequest(status="Completed"), USER))
    run(trail.delete_development_trail_service(1, USER))
    run(guide.delete_interview_guide_service(1, USER))
    run(analysis.delete_resume_analysis_service(1, USER))
    assert [commits(s) for s in (trail, guide, analysis)] == [2, 1, 1]


def test_not_found_never_commits():
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository")

    with pytest.raises(NotFoundException):
        run(service.delete_development_trail_service(1, USER))

    assert commits(service) == 0
