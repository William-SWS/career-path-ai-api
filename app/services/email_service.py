from fastapi import BackgroundTasks

from app.core.config import settings
from app.core.email import send_email
from app.models.user import User
from app.security.tokens import create_reset_password_token


async def send_password_reset_email(user: User, background_tasks: BackgroundTasks):
    token = create_reset_password_token(user.email, user.password_hash)

    reset_url = f"{settings.FRONTEND_HOST}/reset?token={token}"

    data = {
        "app_name": settings.APP_NAME,
        "name": user.name,
        "reset_url": reset_url,
    }

    subject = f"Reset Password - {settings.APP_NAME}"

    await send_email(
        recipients=[user.email],
        subject=subject,
        template_name="password_reset.html",
        context=data,
        background_tasks=background_tasks,
    )
