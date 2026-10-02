"""Verificacion de reCAPTCHA v2 (Google) para registro y login.

Sin esto, alguien puede automatizar la creacion de cuentas o probar
contraseñas a gran escala con un script, sin pasar por un navegador real.
"""
import httpx

from app.config import settings

GOOGLE_SITEVERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class CaptchaInvalido(Exception):
    """Se lanza cuando el token de captcha falta, vencio o Google lo rechaza."""


def verificar_captcha(token: str | None) -> None:
    """Lanza CaptchaInvalido si el token no es valido.

    Si no hay una clave secreta configurada (desarrollo/pruebas locales), no
    se verifica nada: no hace falta una cuenta real de reCAPTCHA para poder
    trabajar en el proyecto sin tocar internet.
    """
    if not settings.recaptcha_secret_key:
        return
    if not token:
        raise CaptchaInvalido("Debes completar el captcha.")
    try:
        respuesta = httpx.post(
            GOOGLE_SITEVERIFY_URL,
            data={"secret": settings.recaptcha_secret_key, "response": token},
            timeout=5.0,
        )
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CaptchaInvalido("No se pudo verificar el captcha. Intenta de nuevo.") from exc
    if not datos.get("success"):
        raise CaptchaInvalido("El captcha no es valido o ya vencio. Intenta de nuevo.")
