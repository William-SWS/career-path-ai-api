class AppException(Exception):
    status_code: int = 400
    default_code: str = "application_error"

    def __init__(
        self, message: str, code: str | None = None, headers: dict[str, str] | None = None
    ):
        self.message = message
        self.code = code or self.default_code
        self.headers = headers
        super().__init__(message)


class ValidationException(AppException):
    status_code = 400
    default_code = "validation_error"


class QueryValidationException(ValidationException):
    default_code = "query_validation_error"


class NotFoundException(AppException):
    status_code = 404
    default_code = "not_found"


class ConflictException(AppException):
    status_code = 409
    default_code = "conflict"


class PermissionDeniedException(AppException):
    status_code = 403
    default_code = "forbidden"


class AuthenticationException(AppException):
    status_code = 401
    default_code = "unauthorized"


class RateLimitException(AppException):
    status_code = 429
    default_code = "rate_limited"


class ServiceUnavailableException(AppException):
    """Uma dependência nossa (ex.: Redis do rate limit) está fora e a operação exige que esteja."""

    status_code = 503
    default_code = "service_unavailable"


class ExternalServiceException(AppException):
    """Falha de um provedor externo (ex.: LLM): indisponível ou resposta inutilizável."""

    status_code = 502
    default_code = "external_service_error"
