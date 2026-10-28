from app.llm.client import GenerationParams
from app.llm.prompts import Prompt, load_system_prompt, untrusted_block

RESUME_ANALYSIS_PARAMS = GenerationParams(
    temperature=0.2, top_p=0.8, top_k=40, max_output_tokens=10000
)

MAX_RESUME_CHARS = 6000


def build_resume_analysis_prompt(resume_text: str) -> Prompt:
    """Monta o prompt de análise de currículo (texto truncado, como dado não confiável)"""
    return Prompt(
        system=load_system_prompt("resume_analysis"),
        user=untrusted_block("curriculo", resume_text[:MAX_RESUME_CHARS]),
    )
