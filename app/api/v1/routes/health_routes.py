# app/routes/health_routes.py
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/")
async def healthcheck():
    """
    Rota para fazer o healthcheck e obter informações gerais da API.
    """
    return {
        "message": "API de Análise de Currículos com Google Gemini",
        "status": "online",
        "model": settings.GEMINI_MODEL,
    }
