import asyncio
import random
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Awaitable, Callable, Protocol

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.llm.prompts import Prompt
from app.core.exceptions import ExternalServiceException, RateLimitException
from app.core.logging_config import logger

# Margem entre o timeout HTTP do SDK e o limite total: o do SDK vale por fase da
# conexão, então o limite externo garante um teto para a chamada inteira.
_HARD_TIMEOUT_MARGIN_SECONDS = 5

# Erros do provedor que costumam passar sozinhos (sobrecarga, falha momentânea).
# 429 fica de fora: é cota esgotada, insistir só gasta a cota e atrasa o aviso ao usuário.
_RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


@dataclass(frozen=True)
class GenerationParams:
    temperature: float
    top_p: float
    top_k: int
    max_output_tokens: int


class LLMClient(Protocol):
    """O que os casos de uso precisam de um modelo: texto de entrada, texto de saída.

    Existe para que os testes usem um FakeLLM determinístico, sem rede.
    """

    async def generate(
        self,
        prompt: Prompt,
        params: GenerationParams,
        response_schema: type[BaseModel] | None = None,
    ) -> str: ...


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int,
        thinking_budget: int = 0,
        max_attempts: int = 3,
        backoff_base_seconds: float = 1.0,
        client: genai.Client | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.thinking_budget = thinking_budget
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self._sleep = sleep
        self._client = client
        if self._client is None and api_key:
            self._client = genai.Client(
                api_key=api_key,
                # O SDK recebe o timeout em milissegundos.
                http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
            )

    async def generate(
        self,
        prompt: Prompt,
        params: GenerationParams,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        if self._client is None:
            # Sem chave só a geração falha; o resto da API continua funcionando.
            raise ExternalServiceException(
                "Serviço de IA indisponível no momento", code="ai_unavailable"
            )

        config = types.GenerateContentConfig(
            temperature=params.temperature,
            top_p=params.top_p,
            top_k=params.top_k,
            max_output_tokens=params.max_output_tokens,
            system_instruction=prompt.system or None,
            # Os tokens de raciocínio contam no max_output_tokens e somam latência.
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget),
        )
        if response_schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema

        started = time.perf_counter()
        try:
            # O teto vale para todas as tentativas juntas: retry nunca alonga a espera do usuário.
            async with asyncio.timeout(self.timeout_seconds + _HARD_TIMEOUT_MARGIN_SECONDS):
                response, attempts = await self._generate_with_retry(prompt.user, config)
        except errors.APIError as exc:
            raise self._translate_api_error(exc)
        except (asyncio.TimeoutError, httpx.TimeoutException):
            logger.error("Timeout de %ss ao chamar o Gemini", self.timeout_seconds)
            raise ExternalServiceException(
                "O serviço de IA demorou demais para responder", code="ai_timeout"
            )
        except httpx.TransportError:
            logger.exception("Falha de rede ao chamar o Gemini")
            raise ExternalServiceException(
                "Serviço de IA indisponível no momento", code="ai_provider_error"
            )

        self._log_usage(response, attempts, time.perf_counter() - started)
        return self._extract_text(response)

    async def _generate_with_retry(self, prompt: str, config: types.GenerateContentConfig):
        attempt = 1
        while True:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                return response, attempt
            except (errors.APIError, httpx.TransportError) as exc:
                if attempt >= self.max_attempts or not self._is_retryable(exc):
                    raise
                # Backoff exponencial com jitter, para não sincronizar retentativas.
                delay = self.backoff_base_seconds * 2 ** (attempt - 1) * random.uniform(0.5, 1.0)
                logger.warning(
                    "Gemini falhou (%s), tentativa %s/%s; nova tentativa em %.1fs",
                    type(exc).__name__, attempt, self.max_attempts, delay,
                )
                await self._sleep(delay)
                attempt += 1

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, errors.APIError):
            return exc.code in _RETRYABLE_STATUS_CODES
        # Timeout não repete: a chamada já consumiu o tempo que o usuário aceitaria esperar.
        return not isinstance(exc, httpx.TimeoutException)

    def _log_usage(self, response: types.GenerateContentResponse, attempts: int, elapsed: float) -> None:
        # Só números: o conteúdo de prompts e respostas tem dados pessoais.
        usage = response.usage_metadata
        logger.info(
            "Gemini ok model=%s latency=%.1fs attempts=%s prompt_tokens=%s output_tokens=%s thought_tokens=%s",
            self.model, elapsed, attempts,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "thoughts_token_count", None),
        )

    @staticmethod
    def _translate_api_error(exc: errors.APIError) -> Exception:
        # O SDK só levanta APIError para respostas HTTP de erro do provedor.
        logger.error("Gemini respondeu com erro %s (%s): %s", exc.code, exc.status, exc.message)

        if exc.code == 429:
            return RateLimitException(
                "Limite de uso do serviço de IA excedido. Tente novamente em alguns minutos.",
                code="ai_quota_exceeded",
            )
        return ExternalServiceException(
            "Serviço de IA indisponível no momento", code="ai_provider_error"
        )

    @staticmethod
    def _extract_text(response: types.GenerateContentResponse) -> str:
        candidates = response.candidates or []
        if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
            logger.warning("Resposta do Gemini foi truncada devido ao limite de tokens")

        # `text` é None quando a resposta foi bloqueada ou veio sem conteúdo.
        text = (response.text or "").strip()
        if not text:
            logger.error(
                "Gemini não devolveu texto (finish_reason=%s)",
                candidates[0].finish_reason if candidates else "sem candidatos",
            )
            raise ExternalServiceException(
                "O serviço de IA devolveu uma resposta inválida", code="ai_invalid_response"
            )

        logger.debug("Resposta bruta do Gemini (primeiros 500 chars): %s", text[:500])
        return text


@lru_cache
def get_llm_client() -> LLMClient:
    """Um cliente por processo: reaproveita o pool de conexões HTTP do SDK."""
    # Import tardio: o módulo do cliente não exige o ambiente completo da API
    # (o script de verificação da chave só precisa de GEMINI_API_KEY).
    from app.core.config import settings

    return GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
        thinking_budget=settings.GEMINI_THINKING_BUDGET,
        max_attempts=settings.GEMINI_MAX_ATTEMPTS,
    )
