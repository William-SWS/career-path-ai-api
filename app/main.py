import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.health_routes import router as health_router
from app.api.v1.routes.router import router as v1_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_POLL_STRATEGY"] = "poll"


app = FastAPI(
    title=settings.APP_NAME,
    description="CareerPath-AI Swagger",
    version="1.0.0",
    debug=settings.DEBUG,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # A API autentica por header Authorization, não por cookie: sem credenciais.
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

register_exception_handlers(app)

app.include_router(v1_router, prefix=settings.API_V1_STR)
# Fora do prefixo da versão: quem sonda a API (orquestrador, load balancer) não depende dela.
app.include_router(health_router)
