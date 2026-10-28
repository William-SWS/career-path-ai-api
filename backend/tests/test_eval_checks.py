"""Os critérios da avaliação manual são código: precisam de teste, ou a avaliação mede a coisa errada."""
import copy

import pytest

from app.schemas.ai_outputs import (
    DevelopmentTrailOutput,
    InterviewGuideOutput,
    ResumeAnalysisOutput,
)
from app.utils.development_trail_utils import calculate_timeframe_months
from evals.cases import CASES
from evals.checks import check_guide, check_resume, check_trail, is_portuguese
from tests.fakes import sample_output

PT = "Plano de estudo para a sua carreira com foco em projetos que você vai fazer"


def results(checks):
    return {name: ok for name, (ok, _) in checks}


def portuguese(output):
    """Troca todo texto de exemplo por português, para isolar o critério em teste."""
    if isinstance(output, str):
        return PT
    if isinstance(output, dict):
        return {k: portuguese(v) if k != "experience_level" else v for k, v in output.items()}
    return [portuguese(v) for v in output]


CASE = next(c for c in CASES if c.name == "junior_backend")


# ---- coerência dos próprios casos ----

@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_expected_phase_count_matches_what_the_prompt_asks_for(case):
    months = calculate_timeframe_months(case.trail.goal_timeframe)
    assert case.expected_phases == (1 if months <= 3 else 2 if months <= 6 else 3)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_resume_skills_expectations_are_consistent_with_the_resume_text(case):
    real_resume = case.resume_text.split("</curriculo>")[0].lower()

    assert all(s.lower() in real_resume for s in case.must_find_skills)
    assert not any(s.lower() in real_resume for s in case.absent_skills)


# ---- critérios ----

def test_language_heuristic():
    assert is_portuguese(PT)
    assert not is_portuguese("The plan is for you and the team to build with the tools")


def test_resume_check_flags_invented_skills_and_wrong_level():
    out = portuguese(sample_output(ResumeAnalysisOutput))
    out["experience_level"] = "Sênior"
    out["technical_skills"]["programming_languages"] = ["Python", "Rust"]
    out["technical_skills"]["databases"] = ["SQL"]

    outcome = results(check_resume(CASE, out))

    assert outcome["encontra_skills_do_curriculo"] is True
    assert outcome["nao_inventa_skills"] is False
    assert outcome["nivel_esperado"] is False


def test_resume_check_flags_missing_real_skills():
    out = portuguese(sample_output(ResumeAnalysisOutput))
    out["experience_level"] = "Júnior"

    assert results(check_resume(CASE, out))["encontra_skills_do_curriculo"] is False


def test_forbidden_terms_are_caught_anywhere_in_the_output():
    injected = next(c for c in CASES if c.forbidden_terms)
    out = portuguese(sample_output(InterviewGuideOutput))
    out["company_specific_preparation"]["research_topics"] = ["hackeado"]  # caixa diferente

    assert results(check_guide(injected, out))["sem_termo_proibido"] is False


def test_guide_check_requires_a_job_requirement_and_non_empty_sections():
    out = portuguese(sample_output(InterviewGuideOutput))
    assert results(check_guide(CASE, out))["toca_requisito_da_vaga"] is False

    out["preparation_overview"] = "Revise Python e APIs REST antes da entrevista para a vaga"
    out["behavioral_preparation"]["common_questions"] = []
    outcome = results(check_guide(CASE, out))
    assert outcome["toca_requisito_da_vaga"] is True
    assert outcome["tem_perguntas_comportamentais"] is False


def test_trail_check_phase_count_availability_and_interest():
    out = portuguese(sample_output(DevelopmentTrailOutput))
    out["study_plan_adaptation"]["for_busy_schedule"] = "Até 15 horas semanais"
    out["career_tips"] = ["Foque em Back-End"]
    assert len(out["development_phases"]) == 1  # o exemplo tem 1 fase; o caso espera 2

    outcome = results(check_trail(CASE, out))
    assert outcome["numero_de_fases"] is False
    assert outcome["repete_disponibilidade"] is True
    assert outcome["cita_interesse_do_usuario"] is True

    out["development_phases"].append(copy.deepcopy(out["development_phases"][0]))
    out["study_plan_adaptation"]["for_busy_schedule"] = "qualquer coisa"
    outcome = results(check_trail(CASE, out))
    assert outcome["numero_de_fases"] is True
    assert outcome["repete_disponibilidade"] is False


def test_empty_strings_are_flagged():
    out = portuguese(sample_output(ResumeAnalysisOutput))
    out["market_insights"] = "  "

    assert results(check_resume(CASE, out))["sem_strings_vazias"] is False
