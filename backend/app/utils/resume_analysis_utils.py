from app.core.config import settings
from app.core.exceptions import ExternalServiceException, RateLimitException
from app.core.logging_config import logger
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import json
import re


def extract_analysis_json_from_text(text: str) -> dict:
    """Extrai JSON do texto de resposta"""
    if not text:
        raise ValueError("Texto vazio não pode ser convertido para JSON")
    
    # Limpa o texto - remove code blocks markdown
    cleaned_text = text.strip()
    cleaned_text = re.sub(r'^```json\s*', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'^```\s*', '', cleaned_text)
    cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    logger.debug(f"Texto limpo para extração JSON (primeiros 300 chars): {cleaned_text[:300]}")
    
    try:
        # Tenta parsear diretamente
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.error(f"Erro no parse JSON direto: {e}")
        
        # Tenta encontrar JSON dentro do texto usando regex
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, cleaned_text, re.DOTALL)
        
        if matches:
            # Pega o maior match (provavelmente o JSON completo)
            json_str = max(matches, key=len)
            logger.debug(f"JSON encontrado via regex (primeiros 300 chars): {json_str[:300]}")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e2:
                logger.error(f"Erro no parse do JSON regex: {e2}")
                
                # Tenta reparar JSON truncado
                try:
                    repaired_json = repair_truncated_json(json_str, e2)
                    if repaired_json:
                        return json.loads(repaired_json)
                except Exception as repair_error:
                    logger.error(f"Falha ao reparar JSON: {repair_error}")
        
        # Se nada funcionar, levanta exceção
        raise ValueError("Não foi possível extrair JSON válido da resposta do modelo")


def repair_truncated_json(json_str: str, error: json.JSONDecodeError = None) -> str:
    """
    Tenta reparar JSON truncado ou com erros de sintaxe
    """
    repaired = json_str.strip()
    
    # Se temos informação sobre o erro, usa para guiar o reparo
    error_pos = None
    if error and hasattr(error, 'pos'):
        error_pos = error.pos
        logger.debug(f"Tentando reparar JSON na posição do erro: {error_pos}")
    
    # Passo 1: Se temos posição do erro, tenta truncar e fechar estruturas nesse ponto
    if error_pos and error_pos > 0:
        truncated = repaired[:error_pos].rstrip()
        while truncated and truncated[-1] in [',', ':', '"']:
            truncated = truncated[:-1].rstrip()
        repaired = truncated
    
    # Passo 2: Repara strings não terminadas
    if repaired.count('"') % 2 != 0:
        last_quote_idx = repaired.rfind('"')
        if last_quote_idx > 0:
            remaining = repaired[last_quote_idx+1:].strip()
            if remaining and not any(c in remaining for c in [':', ',', '}', ']']):
                repaired = repaired[:last_quote_idx+1] + '"' + repaired[last_quote_idx+1:]
    
    # Passo 3: Conta e fecha estruturas não fechadas
    open_braces = repaired.count('{')
    close_braces = repaired.count('}')
    open_brackets = repaired.count('[')
    close_brackets = repaired.count(']')
    
    for _ in range(open_braces - close_braces):
        repaired += '}'
    for _ in range(open_brackets - close_brackets):
        repaired += ']'
    
    # Passo 4: Remove vírgulas finais desnecessárias
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)
    
    # Passo 5: Adiciona vírgulas faltantes em padrões comuns
    repaired = re.sub(r'"\s*\n\s*"', '",\n"', repaired)
    repaired = re.sub(r'}\s*"', '}, "', repaired)
    repaired = re.sub(r']\s*"', '], "', repaired)
    repaired = re.sub(r'"\s*{', '", {', repaired)
    repaired = re.sub(r'"\s*\[', '", [', repaired)
    
    return repaired


async def analyze_with_gemini(resume_text: str) -> dict:
    """Analisa o currículo usando Google Gemini"""

    if not settings.GEMINI_API_KEY:
        raise ExternalServiceException(
            "Serviço de IA indisponível no momento", code="ai_unavailable"
        )

    genai.configure(api_key=settings.GEMINI_API_KEY)

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

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

        response = model.generate_content(
            f"{prompt}\n\nTEXTO DO CURRÍCULO:\n{truncated_text}",
            generation_config=genai.types.GenerationConfig(
                temperature=0.2, 
                max_output_tokens=10000,  # Aumentado para prevenir truncamento
                top_p=0.8, 
                top_k=40
            ),
        )

        # Verifica se a resposta foi truncada
        if hasattr(response.candidates[0], 'finish_reason') and response.candidates[0].finish_reason == 'MAX_OUTPUT_TOKENS':
            logger.warning("Resposta do Gemini foi truncada devido ao limite de tokens")

        response_text = response.text.strip()
        logger.debug(f"Resposta bruta do Gemini (primeiros 500 chars): {response_text[:500]}")

        return extract_analysis_json_from_text(response_text)

    except google_exceptions.ResourceExhausted:
        logger.exception("Quota da API do Gemini excedida ao analisar currículo")
        raise RateLimitException(
            "Limite de uso do serviço de IA excedido. Tente novamente em alguns minutos.",
            code="ai_quota_exceeded",
        )

    except google_exceptions.GoogleAPIError:
        logger.exception("Falha na API do Gemini ao analisar currículo")
        raise ExternalServiceException(
            "Serviço de IA indisponível no momento", code="ai_provider_error"
        )

    except (ValueError, IndexError):
        # Resposta bloqueada, sem candidatos ou sem JSON utilizável.
        logger.exception("Resposta inutilizável do Gemini ao analisar currículo")
        raise ExternalServiceException(
            "O serviço de IA devolveu uma resposta inválida", code="ai_invalid_response"
        )
