"""Regras dos serviços de IA: repositórios em memória e LLM substituído."""
import asyncio
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.core.exceptions import ExternalServiceException, NotFoundException, RateLimitException
from app.schemas.development_trail_schema import (
    DevelopmentTrailRequest,
    DevelopmentTrailUpdateRequest,
)
from tests.fakes import FakeSession
from app.services import (
    development_trail_services,
    interview_guide_services,
    resume_analysis_services,
)
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


def make_service(cls, repository_attr, *records):
    service = cls(db=FakeSession())
    repository = FakeRepository(*records)
    setattr(service, repository_attr, repository)
    return service, repository


def commits(service) -> int:
    return service.db.commits


def stub_llm(monkeypatch, module, name, *, returns=None, raises=None):
    async def fake(*args, **kwargs):
        if raises:
            raise raises
        return returns

    monkeypatch.setattr(module, name, fake)


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

@pytest.mark.parametrize("bad_result", [None, {}, [], "text"], ids=repr)
def test_trail_with_unusable_ai_result_is_not_saved(monkeypatch, bad_result):
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository")
    stub_llm(monkeypatch, development_trail_services, "generate_development_trail_with_gemini", returns=bad_result)

    with pytest.raises(ExternalServiceException) as exc_info:
        run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert exc_info.value.code == "ai_invalid_response"
    assert repo.created == []


def test_trail_is_saved_for_the_requesting_user(monkeypatch):
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository")
    stub_llm(monkeypatch, development_trail_services, "generate_development_trail_with_gemini", returns={"user_profile_summary": {}})

    response = run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert repo.created[0].user_id == USER.id
    assert response.development_trail == {"user_profile_summary": {}}
    assert response.status == "In Progress"


def test_trail_provider_error_propagates_and_nothing_is_saved(monkeypatch):
    service, repo = make_service(DevelopmentTrailService, "development_trail_repository")
    stub_llm(monkeypatch, development_trail_services, "generate_development_trail_with_gemini", raises=RateLimitException("slow down"))

    with pytest.raises(RateLimitException):
        run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert repo.created == []


def test_interview_guide_with_unusable_ai_result_is_not_saved(monkeypatch):
    service, repo = make_service(InterviewGuideService, "interview_guide_repository")
    stub_llm(monkeypatch, interview_guide_services, "check_pdf", returns="cv text")
    stub_llm(monkeypatch, interview_guide_services, "generate_interview_guide_with_gemini", returns={})

    with pytest.raises(ExternalServiceException):
        run(service.generate_interview_guide_service(pdf_upload(), "job", USER))

    assert repo.created == []


def test_interview_guide_is_saved_when_ai_result_is_valid(monkeypatch):
    service, repo = make_service(InterviewGuideService, "interview_guide_repository")
    stub_llm(monkeypatch, interview_guide_services, "check_pdf", returns="cv text")
    stub_llm(monkeypatch, interview_guide_services, "generate_interview_guide_with_gemini", returns={"preparation_overview": "x"})

    response = run(service.generate_interview_guide_service(pdf_upload(), "job", USER))

    assert response.interview_guide == {"preparation_overview": "x"}
    assert len(repo.created) == 1


def test_resume_analysis_with_unusable_ai_result_is_not_saved(monkeypatch):
    service, repo = make_service(ResumeAnalysisService, "resume_analysis_repository")
    stub_llm(monkeypatch, resume_analysis_services, "check_pdf", returns="cv text")
    stub_llm(monkeypatch, resume_analysis_services, "analyze_with_gemini", returns=None)

    with pytest.raises(ExternalServiceException):
        run(service.analyze_resume_service(pdf_upload(), USER))

    assert repo.created == []


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

def test_generating_a_trail_commits_exactly_once(monkeypatch):
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository")
    stub_llm(monkeypatch, development_trail_services, "generate_development_trail_with_gemini", returns={"a": 1})

    run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert commits(service) == 1


def test_unusable_ai_result_commits_nothing(monkeypatch):
    service, _ = make_service(DevelopmentTrailService, "development_trail_repository")
    stub_llm(monkeypatch, development_trail_services, "generate_development_trail_with_gemini", returns={})

    with pytest.raises(ExternalServiceException):
        run(service.generate_development_trail_with_gemini_service(TRAIL_REQUEST, USER))

    assert commits(service) == 0


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
