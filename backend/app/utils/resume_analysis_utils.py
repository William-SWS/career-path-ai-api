from app.llm.client import GenerationParams


RESUME_ANALYSIS_PARAMS = GenerationParams(
    temperature=0.2, top_p=0.8, top_k=40, max_output_tokens=10000
)


def build_resume_analysis_prompt(resume_text: str) -> str:
    """Monta o prompt de análise de currículo (texto truncado)"""
    truncated_text = resume_text[:6000]

    prompt = """
    Você é um especialista em análise de currículos para carreiras em tecnologia. 
    Analise este currículo e retorne APENAS um objeto JSON válido, sem nenhum texto adicional.

    FORMATO EXATO DO JSON:
    {
        "professional_summary": "Resumo profissional em 2-3 frases",
        "experience_level": "Júnior | Pleno | Sênior | Especialista",
        "technical_skills": {
            "programming_languages": ["lista de linguagens encontradas"],
            "frameworks": ["lista de frameworks encontrados"],
            "tools": ["lista de ferramentas encontradas"],
            "databases": ["lista de bancos de dados encontrados"],
            "cloud_services": ["lista de serviços cloud encontrados"]
        },
        "career_recommendations": [
            "Recomendação 1 para crescimento profissional",
            "Recomendação 2 para desenvolvimento de carreira",
            "Recomendação 3 baseada nas habilidades atuais"
        ],
        "skill_gaps": [
            "Habilidade em falta 1 que impediria promoção",
            "Habilidade em falta 2 para mercado atual"
        ],
        "suggested_roles": [
            "Cargo sugerido 1 baseado nas habilidades",
            "Cargo sugerido 2 para próximo nível",
            "Cargo sugerido 3 alinhado com experiência"
        ],
        "market_insights": "Insight sobre mercado de tecnologia para este perfil em 2-3 frases"
    }

    BASEIE-SE APENAS NAS INFORMAÇÕES DO CURRÍCULO.
    """

    return f"{prompt}\n\nTEXTO DO CURRÍCULO:\n{truncated_text}"
