# app/routes/check_routes.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def healthcheck():
    """
    Rota para fazer o healthcheck e obter informações gerais da API.
    """
    return {
        "message": "API de Análise de Currículos com Google Gemini",
        "status": "online",
        "model": "gemini-2.5-flash"
    }