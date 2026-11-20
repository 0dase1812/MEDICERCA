from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.ips import TipoIntegracionIPS


class IPSOut(BaseModel):
    id: int
    codigo: str
    nombre_ficticio: str
    tipo_integracion: TipoIntegracionIPS

    model_config = ConfigDict(from_attributes=True)


class AfiliacionOut(BaseModel):
    ips_id: int
    identificador_paciente_ips: str | None
    vigente_desde: date
    vigente_hasta: date | None
    activa: bool

    model_config = ConfigDict(from_attributes=True)


class IPSCreate(BaseModel):
    """Alta de una IPS nueva. La URL real NUNCA viaja aquí: solo la clave que la resuelve
    en las variables de entorno (ej. 'demo_ips_4' -> DATABASE_URL_IPS_4)."""

    codigo: str = Field(min_length=2, max_length=50)
    nombre_ficticio: str = Field(min_length=2, max_length=150)
    clave_conexion: str = Field(min_length=2, max_length=80)
    tipo_integracion: TipoIntegracionIPS = TipoIntegracionIPS.BASE_DATOS_DIRECTA

    model_config = ConfigDict(extra="forbid")
