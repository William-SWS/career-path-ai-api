"""Critérios objetivos e determinísticos sobre a saída do modelo (sem nota subjetiva automática)."""
from collections.abc import Callable
from typing import Any

from evals.cases import EvalCase

PT_MARKERS = {"de", "para", "com", "em", "uma", "que", "os", "as", "do", "da", "na", "no", "seu", "sua"}
EN_MARKERS = {"the", "and", "with", "for", "of", "to", "is", "your", "you", "will", "that"}


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in flatten_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in flatten_strings(v)]
    return []


def full_text(output: dict) -> str:
    return " \n".join(flatten_strings(output))


def has_empty_strings(output: dict) -> bool:
    return any(not s.strip() for s in flatten_strings(output))


def is_portuguese(text: str) -> bool:
    words = [w.strip(".,;:!?()\"'").lower() for w in text.split()]
    pt = sum(w in PT_MARKERS for w in words)
    en = sum(w in EN_MARKERS for w in words)
    return pt > 3 * en and pt > 0


def mentions(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [t for t in terms if t.lower() in lowered]


def _skills(analysis: dict) -> str:
    return " ".join(flatten_strings(analysis["technical_skills"]))


# Cada critério devolve (passou, detalhe); o detalhe só aparece no relatório quando falha.
Check = Callable[[EvalCase, dict], tuple[bool, str]]


def _common(case: EvalCase, out: dict) -> list[tuple[str, tuple[bool, str]]]:
    text = full_text(out)
    forbidden = mentions(text, case.forbidden_terms)
    return [
        ("portugues", (is_portuguese(text), "saída fora do português")),
        ("sem_strings_vazias", (not has_empty_strings(out), "há campo de texto vazio")),
        ("sem_termo_proibido", (not forbidden, f"apareceu: {forbidden}")),
    ]


def check_trail(case: EvalCase, out: dict) -> list[tuple[str, tuple[bool, str]]]:
    phases = out["development_phases"]
    interests = tuple(case.trail.interested_technologies or [case.trail.professional_goal])
    availability = case.trail.available_time_week
    adaptation = out["study_plan_adaptation"]["for_busy_schedule"]
    return _common(case, out) + [
        ("numero_de_fases", (len(phases) == case.expected_phases, f"{len(phases)} fases, esperado {case.expected_phases}")),
        ("fases_com_projeto_e_topicos", (all(p["projects"] and p["topics"] for p in phases), "fase sem projeto ou tópicos")),
        ("cita_interesse_do_usuario", (bool(mentions(full_text(out), interests)), f"nenhum de {interests}")),
        ("repete_disponibilidade", (availability is None or availability.lower() in adaptation.lower(), f"obtido: {adaptation!r}")),
    ]


def check_resume(case: EvalCase, out: dict) -> list[tuple[str, tuple[bool, str]]]:
    skills = _skills(out)
    missing = [s for s in case.must_find_skills if s.lower() not in skills.lower()]
    invented = mentions(skills, case.absent_skills)
    return _common(case, out) + [
        ("encontra_skills_do_curriculo", (not missing, f"faltou: {missing}")),
        ("nao_inventa_skills", (not invented, f"inventou: {invented}")),
        ("nivel_esperado", (out["experience_level"] in case.expected_levels, f"obtido {out['experience_level']}, aceitos {case.expected_levels}")),
    ]


def check_guide(case: EvalCase, out: dict) -> list[tuple[str, tuple[bool, str]]]:
    return _common(case, out) + [
        ("toca_requisito_da_vaga", (bool(mentions(full_text(out), case.job_keywords)), f"nenhum de {case.job_keywords}")),
        ("tem_perguntas_comportamentais", (bool(out["behavioral_preparation"]["common_questions"]), "lista vazia")),
        ("tem_plano_de_estudo", (bool(out["study_plan_timeline"]["immediate_24h"]), "sem ações nas próximas 24h")),
    ]
