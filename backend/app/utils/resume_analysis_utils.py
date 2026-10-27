from app.core.logging_config import logger
from app.llm.client import GenerationParams
import json
import re


RESUME_ANALYSIS_PARAMS = GenerationParams(
    temperature=0.2, top_p=0.8, top_k=40, max_output_tokens=10000
)


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
