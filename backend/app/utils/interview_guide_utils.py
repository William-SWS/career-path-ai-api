from app.core.config import settings
from app.core.logging_config import logger
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import re
import json


async def generate_interview_guide_with_gemini(resume_text: str, job_description: str) -> dict:
    """Gera um roteiro de entrevista personalizado usando Google Gemini"""
    
    if not settings.GEMINI_API_KEY:
        raise ValueError("Serviço de IA indisponível no momento")
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
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

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        full_prompt = f"""
        {prompt}

        CURRÍCULO:
        {truncated_resume}

        DESCRIÇÃO DA VAGA:
        {truncated_job_desc}

        RESPOSTA (APENAS JSON):
        """
        
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=10000,  # Aumentado para prevenir truncamento
                top_p=0.7,
                top_k=40
            )
        )
        
        # Verifica se a resposta foi truncada
        if hasattr(response.candidates[0], 'finish_reason') and response.candidates[0].finish_reason == 'MAX_OUTPUT_TOKENS':
            logger.warning("Resposta do Gemini foi truncada devido ao limite de tokens")
        
        response_text = response.text.strip()
        logger.debug(f"Resposta bruta do Gemini (primeiros 500 chars): {response_text[:500]}")
        
        # Extrai JSON da resposta
        parsed_response = extract_interview_json_from_text(response_text)
        
        return parsed_response
        
    except google_exceptions.ResourceExhausted:
        logger.exception("Quota da API do Gemini excedida ao gerar guia de entrevista")
        raise ValueError(
            "Limite de uso do serviço de IA excedido. Tente novamente em alguns minutos."
        )

    except Exception:
        logger.exception("Erro ao gerar guia de entrevista")
        raise ValueError("Erro ao gerar guia de entrevista")


def extract_interview_json_from_text(text: str) -> dict:
    """
    Extrai JSON de texto que pode conter markdown ou outros elementos
    Tenta reparar JSON truncado se possível
    """
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
        # Tenta parsear diretamente como JSON
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
                logger.error(f"Erro no parse do JSON regex: {e2} (posição: {e2.pos if hasattr(e2, 'pos') else 'desconhecida'})")
                
                # Tenta reparar JSON truncado
                try:
                    repaired_json = repair_truncated_json(json_str, e2)
                    if repaired_json:
                        return json.loads(repaired_json)
                except Exception as repair_error:
                    logger.error(f"Falha ao reparar JSON: {repair_error}")
                    
                    # Última tentativa: tenta extrair um JSON parcial válido
                    try:
                        partial_json = extract_partial_valid_json(json_str, e2)
                        if partial_json:
                            logger.warning("Usando JSON parcial extraído devido a erro de parsing")
                            return partial_json
                    except Exception as partial_error:
                        logger.error(f"Falha ao extrair JSON parcial: {partial_error}")
        
        # Se nada funcionar, levanta exceção
        raise ValueError("Não foi possível extrair JSON válido da resposta do modelo")


def extract_partial_valid_json(json_str: str, error: json.JSONDecodeError) -> dict:
    """
    Tenta extrair um JSON parcialmente válido mesmo quando há erros
    Usa o JSONDecoder para parsear até onde for possível
    """
    try:
        decoder = json.JSONDecoder()
        # Tenta parsear até a posição do erro
        if hasattr(error, 'pos') and error.pos > 0:
            # Trunca no ponto do erro e tenta parsear o que for possível
            truncated = json_str[:error.pos].rstrip()
            # Remove o último caractere problemático e tenta fechar estruturas
            while truncated and truncated[-1] in ['"', ',', ':', '{', '[', ' ']:
                truncated = truncated[:-1].rstrip()
            # Fecha estruturas não fechadas
            truncated = repair_truncated_json(truncated, None)
            if truncated:
                return json.loads(truncated)
    except Exception:
        pass
    return None


def repair_truncated_json(json_str: str, error: json.JSONDecodeError = None) -> str:
    """
    Tenta reparar JSON truncado ou com erros de sintaxe
    Se um erro específico for fornecido, usa a posição do erro para ajudar no reparo
    """
    repaired = json_str.strip()
    
    # Se temos informação sobre o erro, usa para guiar o reparo
    error_pos = None
    if error and hasattr(error, 'pos'):
        error_pos = error.pos
        logger.debug(f"Tentando reparar JSON na posição do erro: {error_pos}")
    
    # Passo 1: Se temos posição do erro, tenta truncar e fechar estruturas nesse ponto
    if error_pos and error_pos > 0:
        # Tenta truncar antes da posição do erro e fechar estruturas
        truncated = repaired[:error_pos].rstrip()
        # Remove caracteres problemáticos do final
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
    
    # Fecha objetos não fechados
    for _ in range(open_braces - close_braces):
        repaired += '}'
    # Fecha arrays não fechados
    for _ in range(open_brackets - close_brackets):
        repaired += ']'
    
    # Passo 4: Remove vírgulas finais desnecessárias antes de fechamentos
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)
    
    # Passo 5: Adiciona vírgulas faltantes em padrões comuns
    # Entre strings consecutivas em arrays/objetos
    repaired = re.sub(r'"\s*\n\s*"', '",\n"', repaired)  # Adiciona vírgula entre strings em múltiplas linhas
    repaired = re.sub(r'}\s*"', '}, "', repaired)  # Vírgula entre objeto e string
    repaired = re.sub(r']\s*"', '], "', repaired)  # Vírgula entre array e string
    repaired = re.sub(r'"\s*{', '", {', repaired)  # Vírgula entre string e objeto
    repaired = re.sub(r'"\s*\[', '", [', repaired)  # Vírgula entre string e array
    
    return repaired


# Função auxiliar para detectar skills (se ainda precisar)
def detect_skills(text: str, skills_list: list) -> list:
    """Detecta habilidades mencionadas no texto"""
    found_skills = []
    text_lower = text.lower()
    
    for skill in skills_list:
        if skill.lower() in text_lower:
            found_skills.append(skill)
    
    return found_skills
