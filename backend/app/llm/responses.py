from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalServiceException
from app.core.logging_config import logger

T = TypeVar("T", bound=BaseModel)


def parse_structured_response(schema: type[T], text: str) -> T:
    """Valida o texto do modelo contra o schema; resposta fora do contrato é falha do provedor.

    Não tenta consertar JSON truncado ou embrulhado em markdown: com saída
    estruturada isso não deveria acontecer, e consertar às cegas salvaria lixo.
    """
    try:
        return schema.model_validate_json(text)
    except ValidationError as exc:
        # Só tipo e localização dos erros: a mensagem do Pydantic ecoaria o conteúdo gerado.
        problems = [f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors()[:5]]
        logger.error("Resposta do modelo fora do schema %s: %s", schema.__name__, problems)
        raise ExternalServiceException(
            "O serviço de IA devolveu uma resposta inválida", code="ai_invalid_response"
        ) from exc
