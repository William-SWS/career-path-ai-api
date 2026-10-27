from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def build_error_response(status_code: int, message: str, code: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "status": status_code,
                "code": code,
                "message": message,
            }
        },
    )


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
        logger.exception("Unhandled exception: %s", exc_info=exc)
        return build_error_response(
            status_code=500,
            message="Internal server error",
            code="internal_server_error",
        )