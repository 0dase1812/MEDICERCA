"""Envio de correos reales via la API de Brevo.

Mientras EMAIL_MODO sea "simulado" (o no haya BREVO_API_KEY configurada),
esta funcion no hace nada: el codigo de verificacion sigue viniendo en la
respuesta (`codigo_demo`) como hasta ahora, para poder trabajar localmente
sin necesitar una cuenta de correo real.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def enviar_correo(destinatario: str, asunto: str, cuerpo_html: str) -> None:
    if settings.email_modo != "real" or not settings.brevo_api_key:
        return

    payload = {
        "sender": {"name": settings.email_remitente_nombre, "email": settings.email_remitente},
        "to": [{"email": destinatario}],
        "subject": asunto,
        "htmlContent": cuerpo_html,
    }
    try:
        respuesta = httpx.post(
            BREVO_API_URL,
            json=payload,
            headers={"api-key": settings.brevo_api_key, "content-type": "application/json"},
            timeout=10.0,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError:
        # No se propaga el error: que falle el envio de un correo no debe
        # tumbar la operacion real (registrar usuario, aprobar orden, etc.).
        logger.exception("No se pudo enviar el correo a %s", destinatario)
