import asyncio

from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, MessageType

from app.core.config import conf
from app.core.logging_config import logger

# Esperas entre as tentativas de envio: 1 envio + 2 novas tentativas.
_RETRY_DELAYS_SECONDS = (1, 3)


async def _deliver(fm: FastMail, message: MessageSchema, template_name: str) -> None:
    """
    Envia o e-mail, repetindo em falhas passageiras do SMTP. Roda depois da resposta,
    então nenhuma exceção pode escapar. Os logs trazem só o assunto e o tipo do erro:
    a mensagem do SMTP pode conter o endereço do destinatário.
    """
    attempts = len(_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(1, attempts + 1):
        try:
            await fm.send_message(message, template_name=template_name)
            return
        except Exception as exc:
            if attempt == attempts:
                logger.error(
                    "Falha ao enviar e-mail %r após %d tentativas (%s)",
                    message.subject,
                    attempts,
                    type(exc).__name__,
                )
                return
            logger.warning(
                "Falha ao enviar e-mail %r (tentativa %d de %d, %s); tentando de novo",
                message.subject,
                attempt,
                attempts,
                type(exc).__name__,
            )
            await asyncio.sleep(_RETRY_DELAYS_SECONDS[attempt - 1])


def send_email(
    recipients: list,
    subject: str,
    context: dict,
    template_name: str,
    background_tasks: BackgroundTasks,
) -> None:
    """Agenda o envio para depois da resposta; não espera o SMTP."""
    message = MessageSchema(
        subject=subject, recipients=recipients, template_body=context, subtype=MessageType.html
    )

    background_tasks.add_task(_deliver, FastMail(conf), message, template_name)
