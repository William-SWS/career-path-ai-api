from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, MessageType

from app.core.config import conf


async def send_email(
    recipients: list,
    subject: str,
    context: dict,
    template_name: str,
    background_tasks: BackgroundTasks,
):
    fm = FastMail(conf)

    message = MessageSchema(
        subject=subject, recipients=recipients, template_body=context, subtype=MessageType.html
    )

    background_tasks.add_task(fm.send_message, message, template_name=template_name)
