"""Contrato do que o modelo deve devolver em cada caso de uso.

O mesmo modelo Pydantic é enviado ao Gemini como `response_schema` (o provedor
restringe a geração ao formato) e valida a resposta antes de salvar. As chaves
são as que já ficam gravadas no banco e que o frontend lê; não renomear sem migrar.
"""

from typing import Literal

from pydantic import BaseModel

# ---- trilha de desenvolvimento ----


class UserProfileSummary(BaseModel):
    current_profile: str
    strengths: list[str]
    improvement_areas: list[str]


class DevelopmentPhase(BaseModel):
    phase: str
    duration: str
    focus: str
    topics: list[str]
    resources: list[str]
    projects: list[str]
    learning_outcomes: list[str]


class RecommendedResources(BaseModel):
    courses: list[str]
    tools: list[str]
    communities: list[str]
    books: list[str]


class Milestone(BaseModel):
    timeline: str
    goals: list[str]
    success_indicators: list[str]


class StudyPlanAdaptation(BaseModel):
    for_busy_schedule: str
    weekly_recommendation: str
    acceleration_tips: list[str]


class DevelopmentTrailOutput(BaseModel):
    user_profile_summary: UserProfileSummary
    development_phases: list[DevelopmentPhase]
    recommended_resources: RecommendedResources
    milestones: list[Milestone]
    career_tips: list[str]
    study_plan_adaptation: StudyPlanAdaptation


# ---- guia de entrevista ----


class StrengthAnalysis(BaseModel):
    key_strengths: list[str]
    alignment_points: list[str]


class LanguagePreparation(BaseModel):
    topic: str
    focus_points: list[str]
    expected_level: str


class FrameworkPreparation(BaseModel):
    topic: str
    key_concepts: list[str]
    practical_examples: list[str]


class SystemDesignPreparation(BaseModel):
    topic: str
    preparation_guide: str


class TechnicalPreparation(BaseModel):
    programming_languages: list[LanguagePreparation]
    frameworks_tools: list[FrameworkPreparation]
    system_design: list[SystemDesignPreparation]


class StorytellingPoint(BaseModel):
    situation: str
    key_achievements: list[str]
    metrics: str


class CommonQuestion(BaseModel):
    question: str
    preparation_tips: str
    resume_connection: str


class BehavioralPreparation(BaseModel):
    storytelling_points: list[StorytellingPoint]
    common_questions: list[CommonQuestion]


class CompanySpecificPreparation(BaseModel):
    research_topics: list[str]
    questions_to_ask: list[str]


class StudyPlanTimeline(BaseModel):
    immediate_24h: list[str]
    next_3_days: list[str]
    week_before: list[str]


class InterviewGuideOutput(BaseModel):
    preparation_overview: str
    strength_analysis: StrengthAnalysis
    technical_preparation: TechnicalPreparation
    behavioral_preparation: BehavioralPreparation
    company_specific_preparation: CompanySpecificPreparation
    study_plan_timeline: StudyPlanTimeline


# ---- análise de currículo ----


class TechnicalSkills(BaseModel):
    programming_languages: list[str]
    frameworks: list[str]
    tools: list[str]
    databases: list[str]
    cloud_services: list[str]


class ResumeAnalysisOutput(BaseModel):
    professional_summary: str
    experience_level: Literal["Júnior", "Pleno", "Sênior", "Especialista"]
    technical_skills: TechnicalSkills
    career_recommendations: list[str]
    skill_gaps: list[str]
    suggested_roles: list[str]
    market_insights: str
