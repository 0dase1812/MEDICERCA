"""Captcha (reCAPTCHA) en registro/login, y envio de correo real (Brevo).

Ambos quedan "apagados" por defecto (sin RECAPTCHA_SECRET_KEY ni
BREVO_API_KEY configuradas) para no depender de internet ni de cuentas
reales en desarrollo/pruebas — por eso el resto de la suite de tests sigue
pasando sin tocar nada de este archivo. Aqui se prueba el comportamiento
cuando SI estan configuradas, simulando las respuestas externas (Google,
Brevo) para no hacer llamadas de red reales."""
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.email import enviar_correo


def _registro_payload(**cambios: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Ana Captcha",
        "cedula": "4040404040",
        "correo": "ana.captcha@correo.com",
        "password": "ClaveSegura123",
        "ips_id": 1,
    }
    payload.update(cambios)
    return payload


@pytest.fixture
def con_captcha_activado(monkeypatch):
    monkeypatch.setattr(settings, "recaptcha_secret_key", "clave-secreta-de-prueba")
    yield
    monkeypatch.setattr(settings, "recaptcha_secret_key", "")


def _respuesta_mock(exito: bool) -> httpx.Response:
    return httpx.Response(200, json={"success": exito}, request=httpx.Request("POST", "https://x"))


def test_sin_clave_configurada_no_se_exige_captcha(client: TestClient) -> None:
    """Comportamiento por defecto (desarrollo/pruebas): sin RECAPTCHA_SECRET_KEY,
    el registro funciona igual sin importar que no se mande captcha_token."""
    response = client.post("/api/v1/auth/register", json=_registro_payload())
    assert response.status_code == 201


def test_registro_rechaza_sin_captcha_token_cuando_esta_activado(
    client: TestClient, con_captcha_activado
) -> None:
    response = client.post("/api/v1/auth/register", json=_registro_payload())
    assert response.status_code == 422
    assert "captcha" in response.json()["detail"].lower()


def test_registro_rechaza_captcha_invalido(client: TestClient, con_captcha_activado) -> None:
    with patch("app.core.captcha.httpx.post", return_value=_respuesta_mock(exito=False)):
        response = client.post(
            "/api/v1/auth/register",
            json=_registro_payload(captcha_token="token-malo"),
        )
    assert response.status_code == 422


def test_registro_acepta_captcha_valido(client: TestClient, con_captcha_activado) -> None:
    with patch("app.core.captcha.httpx.post", return_value=_respuesta_mock(exito=True)):
        response = client.post(
            "/api/v1/auth/register",
            json=_registro_payload(captcha_token="token-bueno"),
        )
    assert response.status_code == 201


def test_login_rechaza_sin_captcha_token_cuando_esta_activado(
    client: TestClient, con_captcha_activado
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"correo": "alguien@correo.com", "password": "ClaveSegura123"},
    )
    assert response.status_code == 422


def test_enviar_correo_no_hace_nada_sin_configurar(monkeypatch) -> None:
    """Modo por defecto: email_modo='simulado' (o sin BREVO_API_KEY) -> no debe
    intentar ninguna llamada de red."""
    with patch("app.core.email.httpx.post") as mock_post:
        enviar_correo("alguien@correo.com", "Asunto", "<p>cuerpo</p>")
    mock_post.assert_not_called()


def test_enviar_correo_llama_a_brevo_cuando_esta_configurado(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_modo", "real")
    monkeypatch.setattr(settings, "brevo_api_key", "clave-brevo-de-prueba")
    respuesta_mock = httpx.Response(201, json={}, request=httpx.Request("POST", "https://x"))
    with patch("app.core.email.httpx.post", return_value=respuesta_mock) as mock_post:
        enviar_correo("paciente@correo.com", "Asunto de prueba", "<p>cuerpo</p>")
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["to"] == [{"email": "paciente@correo.com"}]
    assert kwargs["headers"]["api-key"] == "clave-brevo-de-prueba"
