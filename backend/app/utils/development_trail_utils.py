from app.schemas.development_trail_schema import DevelopmentTrailRequest
from app.llm.client import GenerationParams
import re


DEVELOPMENT_TRAIL_PARAMS = GenerationParams(
    temperature=0.3, top_p=0.8, top_k=40, max_output_tokens=10000
)


def create_adaptive_development_trail_prompt(user_data: DevelopmentTrailRequest) -> str:
    """Cria um prompt adaptável baseado no tempo disponível do usuário"""

    # Calcula meses totais baseado no timeframe
    total_months = calculate_timeframe_months(user_data.goal_timeframe)

    # Define estrutura de fases baseada no tempo disponível
    phases_structure = get_phases_structure(total_months)

    return f"""
Você é um especialista em desenvolvimento de carreira em tecnologia. 
Analise os dados do usuário e retorne APENAS um objeto JSON válido, sem nenhum texto adicional.

**DADOS DO USUÁRIO:**
- Nome: {user_data.name}
- Idade: {user_data.age or "Não informada"}
- Formação: {user_data.education or "Não informada"}
- Área Atual: {user_data.current_area or "Não informada"}
- Experiência: {user_data.experience_in_years or 0} anos
- Habilidades: {", ".join(user_data.skills)}
- Tecnologias de Interesse: {", ".join(user_data.interested_technologies) if user_data.interested_technologies else "Não informado"}
- Nível Atual: {user_data.current_level or "Não informado"}
- Objetivo Profissional: {user_data.professional_goal}
- Disponibilidade Semanal: {user_data.available_time_week or "Não informada"}
- Prazo para Objetivo: {user_data.goal_timeframe or "Não informado"}
- Informações Adicionais: {user_data.additional_information or "Nenhuma"}

**ESTRUTURA ADAPTATIVA ({total_months} meses):**
{phases_structure}

**FORMATO EXATO DO JSON:**

{{
    "user_profile_summary": {{
        "current_profile": "Resumo do perfil atual em 2-3 frases",
        "strengths": ["ponto forte 1", "ponto forte 2", "ponto forte 3"],
        "improvement_areas": ["área de melhoria 1", "área de melhoria 2"]
    }},
    "development_phases": [
        {{
            "phase": "NOME_DA_FASE",
            "duration": "X-Y semanas/meses",
            "focus": "Foco principal desta fase",
            "topics": ["tópico 1", "tópico 2", "tópico 3"],
            "resources": ["recurso 1", "recurso 2"],
            "projects": ["projeto prático 1", "projeto prático 2"],
            "learning_outcomes": ["resultado 1", "resultado 2"]
        }}
        // REPETIR PARA CADA FASE DEFINIDA NA ESTRUTURA
    ],
    "recommended_resources": {{
        "courses": ["curso 1", "curso 2", "curso 3"],
        "tools": ["ferramenta 1", "ferramenta 2"],
        "communities": ["comunidade 1", "comunidade 2"],
        "books": ["livro 1", "livro 2"]
    }},
    "milestones": [
        {{
            "timeline": "Mês X/Final da Fase Y",
            "goals": ["meta específica 1", "meta específica 2"],
            "success_indicators": ["indicador 1", "indicador 2"]
        }}
        // ADAPTAR OS MILESTONES À DURAÇÃO TOTAL
    ],
    "career_tips": [
        "dica prática 1",
        "dica prática 2", 
        "dica prática 3",
        "dica prática 4"
    ],
    "study_plan_adaptation": {{
        "for_busy_schedule": "{user_data.available_time_week}",
        "weekly_recommendation": "Recomendação de estudo semanal adaptada",
        "acceleration_tips": ["Dica para acelerar 1", "Dica para acelerar 2"]
    }}
}}

**INSTRUÇÕES ADAPTATIVAS:**

DURAÇÃO TOTAL: {total_months} MESES
- Se {total_months} <= 3 meses: Foque em objetivos imediatos e habilidades essenciais
- Se 4 <= {total_months} <= 6 meses: Inclua fundamentos + especialização básica  
- Se {total_months} >= 7 meses: Crie um plano completo com múltiplas fases de aprofundamento

DISPONIBILIDADE: {user_data.available_time_week or "Não especificada"}
- Se < 10h/semana: Priorize micro-learning e projetos pequenos
- Se 10-20h/semana: Mantenha ritmo moderado com projetos medianos
- Se > 20h/semana: Inclua projetos complexos e aprendizagem aprofundada

NÍVEL: {user_data.current_level or "Não especificado"}
- Iniciante: Foque em fundamentos e projetos guiados
- Intermediário: Balance fundamentos com especialização
- Avançado: Foque em tópicos avançados e projetos complexos

**REGRAS ESTRITAS:**
1. BASEIE-SE APENAS NAS INFORMAÇÕES FORNECIDAS
2. SEJA REALISTA com o tempo disponível
3. PRIORIZE as tecnologias de interesse: {user_data.interested_technologies or "Todas"}
4. ADAPTE a complexidade ao nível do usuário
5. INCLUA projetos PRÁTICOS em cada fase
"""


def calculate_timeframe_months(timeframe: str) -> int:
    """Calcula meses totais baseado no timeframe informado"""
    if not timeframe:
        return 6  # default

    timeframe_lower = timeframe.lower()

    if any(term in timeframe_lower for term in ["1 mes", "1 mês", "30 dias", "um mes"]):
        return 1
    elif any(term in timeframe_lower for term in ["3 meses", "trimestre", "90 dias"]):
        return 3
    elif any(term in timeframe_lower for term in ["6 meses", "semestre", "180 dias"]):
        return 6
    elif any(term in timeframe_lower for term in ["1 ano", "12 meses", "365 dias"]):
        return 12
    elif any(term in timeframe_lower for term in ["2 anos", "24 meses"]):
        return 24
    else:
        numbers = re.findall(r"\d+", timeframe)
        if numbers:
            return min(int(numbers[0]), 36)
        return 6 


def get_phases_structure(total_months: int) -> str:
    """Retorna a estrutura de fases baseada na duração total"""

    if total_months <= 3:
        return """
        FASE ÚNICA ({} meses): Desenvolvimento Acelerado
        - Foco: Objetivos imediatos e habilidades mais críticas
        - Projetos: Pequenos e focados
        - Entrega: MVP do conhecimento necessário
        """.format(total_months)

    elif total_months <= 6:
        return """
        FASE 1 (2-3 meses): Fundamentos Sólidos
        FASE 2 ({} meses): Especialização Prática
        - Balance entre teoria e prática
        - Projetos intermediários
        """.format(total_months - 2)

    else:  # 7+ meses
        return """
        FASE 1 (2-3 meses): Fundamentos Avançados
        FASE 2 (3-4 meses): Especialização Técnica  
        FASE 3 ({} meses): Aprofundamento e Projetos Complexos
        - Abordagem completa e aprofundada
        - Projetos de portfólio robustos
        """.format(total_months - 5)
