from typing import Callable

from app.core.exceptions import ExternalServiceException
from app.core.logging_config import logger


def parse_json_response(parser: Callable[[str], dict], text: str) -> dict:
    """Aplica o parser de JSON do caso de uso; uma resposta sem JSON utilizável é falha do provedor."""
    try:
        result = parser(text)
    except ValueError:
        logger.exception("Resposta do modelo sem JSON utilizável")
        result = None

    if not result or not isinstance(result, dict):
        raise ExternalServiceException(
            "O serviço de IA devolveu uma resposta inválida", code="ai_invalid_response"
        )

    return result
