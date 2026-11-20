from datetime import date

from pydantic import BaseModel, Field


class ResultadoDisponibilidad(BaseModel):
    ips_id: int
    ips_nombre: str
    punto_id: int
    punto_nombre: str
    ciudad: str
    direccion: str
    lat: float
    lng: float
    # Distancia en línea recta desde el usuario (km). Sirve para mostrar "a 1,2 km".
    distancia_km: float
    cantidad: int
    fecha_reabastecimiento: date | None
    nivel: str  # "punto_mas_cercano" | "otro_punto_ciudad" | "otra_ciudad" | "no_disponible"


class IPSNoDisponible(BaseModel):
    ips_id: int
    ips_nombre: str


class RespuestaDisponibilidad(BaseModel):
    """Resultados de las IPS que respondieron + aviso de las que no (degradación elegante)."""

    resultados: list[ResultadoDisponibilidad]
    ips_no_disponibles: list[IPSNoDisponible] = []
    aviso: str | None = None


class ConsultaDisponibilidad(BaseModel):
    medicamento_id: int
    lat_usuario: float = Field(ge=-90, le=90)
    lng_usuario: float = Field(ge=-180, le=180)
    ciudad_usuario: str
