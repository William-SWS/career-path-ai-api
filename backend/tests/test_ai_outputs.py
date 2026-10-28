"""As chaves dos schemas são o contrato com o banco e o frontend: mudar uma é mudar os dois."""
import pytest

from app.schemas.ai_outputs import (
    DevelopmentTrailOutput,
    InterviewGuideOutput,
    ResumeAnalysisOutput,
)


@pytest.mark.parametrize(
    "schema, keys",
    [
        (DevelopmentTrailOutput, {"user_profile_summary", "development_phases", "recommended_resources",
                                  "milestones", "career_tips", "study_plan_adaptation"}),
        (InterviewGuideOutput, {"preparation_overview", "strength_analysis", "technical_preparation",
                                "behavioral_preparation", "company_specific_preparation", "study_plan_timeline"}),
        (ResumeAnalysisOutput, {"professional_summary", "experience_level", "technical_skills",
                                "career_recommendations", "skill_gaps", "suggested_roles", "market_insights"}),
    ],
)
def test_top_level_keys_are_the_ones_the_app_already_stores(schema, keys):
    assert set(schema.model_fields) == keys


def test_frontend_reads_these_nested_keys():
    phase = set(DevelopmentTrailOutput.model_fields["development_phases"].annotation.__args__[0].model_fields)
    assert {"phase", "duration", "focus", "topics", "projects", "learning_outcomes"} <= phase
