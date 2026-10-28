from app.llm.client import GenerationParams
from app.llm.prompts import Prompt, load_system_prompt, untrusted_block

INTERVIEW_GUIDE_PARAMS = GenerationParams(
    temperature=0.2, top_p=0.7, top_k=40, max_output_tokens=10000
)

MAX_RESUME_CHARS = 6000
MAX_JOB_DESCRIPTION_CHARS = 2000


def build_interview_guide_prompt(resume_text: str, job_description: str) -> Prompt:
    """Monta o prompt do guia de entrevista (currículo e vaga truncados, como dados não confiáveis)"""
    return Prompt(
        system=load_system_prompt("interview_guide"),
        user=(
            untrusted_block("curriculo", resume_text[:MAX_RESUME_CHARS])
            + "\n\n"
            + untrusted_block("vaga", job_description[:MAX_JOB_DESCRIPTION_CHARS])
        ),
    )
