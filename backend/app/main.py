from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.tasks import start_token_cleanup_scheduler, scheduler
from app.core.exception_handlers import register_exception_handlers
from app.api.v1.routes.router import router as v1_router

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_POLL_STRATEGY"] = "poll"


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_token_cleanup_scheduler()

    yield

    if scheduler and scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    description="CareerPath-AI Swagger",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    }
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(v1_router, prefix=settings.API_V1_STR)