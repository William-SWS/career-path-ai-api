from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.core.config import settings, conf
from app.models.user import User
from app.utils.token_utils import create_reset_password_token 


async def send_email(recipients: list, subject: str, context: dict, template_name: str, background_tasks: BackgroundTasks):
    fm = FastMail(conf)

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        template_body=context,
        subtype=MessageType.html
    )

    background_tasks.add_task(fm.send_message, message, template_name=template_name)

async def send_password_reset_email(user: User, background_tasks: BackgroundTasks):
    token = create_reset_password_token(user.email)

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
        background_tasks=background_tasks
    )
