from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.security import validar_fortaleza_password
from app.models.usuario import RolUsuario


class UsuarioCreate(BaseModel):
    """Payload accepted by the public registration endpoint.

    The role is deliberately absent: public accounts are always patients.
    Regente accounts must be provisioned by an administrator or a seed command.
    """
    nombre: str
    cedula: str
    correo: EmailStr
    password: str
    eps_id: int | None = None
    ips_id: int | None = None
    # Token que devuelve el widget de reCAPTCHA en el navegador. Si el
    # servidor no tiene una clave secreta configurada, se ignora.
    captcha_token: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def _validar_password(cls, v: str) -> str:
        return validar_fortaleza_password(v)


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    cedula: str
    correo: EmailStr
    eps_id: int | None
    ips_id: int | None
    rol: RolUsuario
    verificado: bool

    model_config = ConfigDict(from_attributes=True)


class RegistroOut(BaseModel):
    usuario: UsuarioOut
    mensaje: str
    codigo_demo: str | None = None  # solo se llena en modo "simulado"; en modo "real" queda en None


class VerificarCodigoRequest(BaseModel):
    correo: EmailStr
    codigo: str


class SolicitarCambioPasswordRequest(BaseModel):
    correo: EmailStr


class SolicitarCambioPasswordOut(BaseModel):
    mensaje: str
    codigo_demo: str | None = None


class ConfirmarCambioPasswordRequest(BaseModel):
    correo: EmailStr
    codigo: str
    nueva_password: str

    @field_validator("nueva_password")
    @classmethod
    def _validar_password(cls, v: str) -> str:
        return validar_fortaleza_password(v)


class LoginRequest(BaseModel):
    correo: EmailStr
    password: str
    captcha_token: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCrearRegenteRequest(BaseModel):
    """Payload for the admin-only regente provisioning endpoint (see routes/admin.py)."""
    nombre: str
    cedula: str
    correo: EmailStr
    password: str
    ips_id: int | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def _validar_password(cls, v: str) -> str:
        return validar_fortaleza_password(v)
