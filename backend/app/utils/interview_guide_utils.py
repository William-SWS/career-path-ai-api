from app.llm.client import GenerationParams


INTERVIEW_GUIDE_PARAMS = GenerationParams(
    temperature=0.2, top_p=0.7, top_k=40, max_output_tokens=10000
)


def build_interview_guide_prompt(resume_text: str, job_description: str) -> str:
    """Monta o prompt do guia de entrevista (currículo e vaga truncados)"""
    truncated_resume = resume_text[:6000]
    truncated_job_desc = job_description[:2000]

    prompt = """
    VOCÊ É UM ESPECIALISTA EM PREPARAÇÃO PARA ENTREVISTAS DE TECNOLOGIA. 

    **INSTRUÇÃO CRÍTICA: RETORNE APENAS UM OBJETO JSON VÁLIDO. NADA MAIS. SEM TEXTOS EXPLICATIVOS, SEM COMENTÁRIOS, SEM MARKDOWN.**

    ANALISE O CURRÍCULO E A DESCRIÇÃO DA VAGA E RETORNE UM ROTEIRO COMPLETO DE ENTREVISTA NO SEGUINTE FORMATO EXATO:

    {
        "preparation_overview": "string com visão geral de 2-3 frases",
        "strength_analysis": {
            "key_strengths": ["string1", "string2", "string3"],
            "alignment_points": ["string1", "string2"]
        },
        "technical_preparation": {
            "programming_languages": [
                {
                    "topic": "string",
                    "focus_points": ["string1", "string2", "string3"],
                    "expected_level": "string"
                }
            ],
            "frameworks_tools": [
                {
                    "topic": "string",
                    "key_concepts": ["string1", "string2"],
                    "practical_examples": ["string1", "string2"]
                }
            ],
            "system_design": [
                {
                    "topic": "string",
                    "preparation_guide": "string"
                }
            ]
        },
        "behavioral_preparation": {
            "storytelling_points": [
                {
                    "situation": "string",
                    "key_achievements": ["string1", "string2"],
                    "metrics": "string"
                }
            ],
            "common_questions": [
                {
                    "question": "string",
                    "preparation_tips": "string",
                    "resume_connection": "string"
                }
            ]
        },
        "company_specific_preparation": {
            "research_topics": ["string1", "string2"],
            "questions_to_ask": ["string1", "string2", "string3"]
        },
        "study_plan_timeline": {
            "immediate_24h": ["string1", "string2"],
            "next_3_days": ["string1", "string2", "string3"],
            "week_before": ["string1", "string2"]
        }
    }

    **REGRAS:**
    - PREENCHA TODOS OS CAMPOS
    - BASEIE-SE APENAS NAS INFORMAÇÕES DO CURRÍCULO E VAGA
    - SEJA ESPECÍFICO E DIRETO
    - NÃO INCLUA TEXTOS EXPLICATIVOS FORA DO JSON
    - MANTENHA O FORMATO EXATO ACIMA
    """

    return f"""
    {prompt}

    CURRÍCULO:
    {truncated_resume}

    DESCRIÇÃO DA VAGA:
    {truncated_job_desc}

    RESPOSTA (APENAS JSON):
    """
