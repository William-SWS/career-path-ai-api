from apscheduler.schedulers.background import BackgroundScheduler
from app.utils.token_utils import cleanup_expired_tokens
from app.core.database import get_db_sync
from app.core.logging_config import logger

scheduler = BackgroundScheduler()


def scheduled_cleanup_job():
    """
    Executa a limpeza com criação e fechamento de sessão.
    """
    db = next(get_db_sync())
    try:
        cleanup_expired_tokens(db)
        db.commit()
    except Exception as e:
        logger.error(f"Erro ao limpar tokens expirados: {e}")
        db.rollback()
    finally:
        db.close()


def start_token_cleanup_scheduler():
    """
    Inicia o scheduler de limpeza de tokens
    """
    if not scheduler.running:
        scheduler.add_job(
            scheduled_cleanup_job,
            "interval",
            hours=24,
        )
        scheduler.start()
