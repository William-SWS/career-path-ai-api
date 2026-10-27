from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def build_error_response(
    status_code: int, message: str, code: str, details: list[dict] | None = None
):
    error = {"status": status_code, "code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def _validation_details(exc: RequestValidationError) -> list[dict]:
    """Um item por campo inválido, sem expor o input recebido."""
    return [
        {
            "field": ".".join(str(part) for part in error["loc"][1:]),
            "message": error["msg"].removeprefix("Value error, "),
        }
        for error in exc.errors()
    ]


def register_exception_handlers(app):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return build_error_response(
            status_code=exc.status_code,
            message=exc.message,
            code=exc.code,
        )
    

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return build_error_response(
            status_code=422,
            message="Request validation error",
            code="request_validation_error",
            details=_validation_details(exc),
        )


    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return build_error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            code="http_error",
        )


    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        return build_error_response(
            status_code=500,
            message="Internal server error",
            code="internal_server_error",
        )