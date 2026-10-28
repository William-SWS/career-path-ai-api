import re

from app.llm.client import GenerationParams
from app.llm.prompts import Prompt, load_system_prompt, untrusted_block
from app.schemas.development_trail_schema import DevelopmentTrailRequest

DEVELOPMENT_TRAIL_PARAMS = GenerationParams(
    temperature=0.3, top_p=0.8, top_k=40, max_output_tokens=10000
)


def create_adaptive_development_trail_prompt(user_data: DevelopmentTrailRequest) -> Prompt:
    """Monta o prompt da trilha: instruções fixas no system, plano calculado e dados do usuário na mensagem"""
    total_months = calculate_timeframe_months(user_data.goal_timeframe)

    # Os campos abaixo são digitados pelo usuário e vão como dado não confiável.
    user_fields = f"""- Nome: {user_data.name}
- Idade: {user_data.age or "Não informada"}
- Formação: {user_data.education or "Não informada"}
- Área Atual: {user_data.current_area or "Não informada"}
- Experiência: {f"{user_data.experience_in_years} anos" if user_data.experience_in_years is not None else "Não informada"}
- Habilidades: {", ".join(user_data.skills)}
- Tecnologias de Interesse: {", ".join(user_data.interested_technologies) if user_data.interested_technologies else "Não informado"}
- Nível Atual: {user_data.current_level or "Não informado"}
- Objetivo Profissional: {user_data.professional_goal}
- Disponibilidade Semanal: {user_data.available_time_week or "Não informada"}
- Prazo para Objetivo: {user_data.goal_timeframe or "Não informado"}
- Informações Adicionais: {user_data.additional_information or "Nenhuma"}"""

    # Plano derivado só de um número calculado em código, não do texto do usuário.
    plan = f"DURAÇÃO TOTAL: {total_months} MESES\n{get_phases_structure(total_months)}"

    return Prompt(
        system=load_system_prompt("development_trail"),
        user=(
            f"<estrutura_do_plano>\n{plan}\n</estrutura_do_plano>\n\n"
            + untrusted_block("dados_usuario", user_fields)
        ),
    )


def calculate_timeframe_months(timeframe: str | None) -> int:
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
        return f"""
        FASE ÚNICA ({total_months} meses): Desenvolvimento Acelerado
        - Foco: Objetivos imediatos e habilidades mais críticas
        - Projetos: Pequenos e focados
        - Entrega: MVP do conhecimento necessário
        """

    elif total_months <= 6:
        return f"""
        FASE 1 (2-3 meses): Fundamentos Sólidos
        FASE 2 ({total_months - 2} meses): Especialização Prática
        - Balance entre teoria e prática
        - Projetos intermediários
        """

    else:  # 7+ meses
        return f"""
        FASE 1 (2-3 meses): Fundamentos Avançados
        FASE 2 (3-4 meses): Especialização Técnica
        FASE 3 ({total_months - 5} meses): Aprofundamento e Projetos Complexos
        - Abordagem completa e aprofundada
        - Projetos de portfólio robustos
        """
