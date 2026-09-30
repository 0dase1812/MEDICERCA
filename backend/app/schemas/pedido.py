from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models_ips import EstadoDomicilio, EstadoOrden

# La orden ya no se crea con un payload JSON: el paciente sube el archivo
# de la fórmula (imagen o PDF) como multipart/form-data — ver
# app.api.v1.routes.ordenes.cargar_orden, que recibe Form(...)/File(...)
# directamente en vez de un modelo Pydantic de request body.


class OrdenMedicaOut(BaseModel):
    id: int
    usuario_cedula: str
    archivo_url: str
    medicamento_id: int
    estado: EstadoOrden
    revisado_por: str | None
    creado_en: datetime
    aprobado_en: datetime | None

    model_config = ConfigDict(from_attributes=True)


class HistorialEstadoOrdenOut(BaseModel):
    estado: EstadoOrden
    revisado_por: str | None
    registrado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class DomicilioCreate(BaseModel):
    ips_id: int
    orden_id: int
    punto_origen_id: int
    medicamento_id: int  # para poder validar la regla legal (control especial / RX)


class DomicilioOut(BaseModel):
    id: int
    orden_id: int
    punto_origen_id: int
    estado: EstadoDomicilio
    eta: datetime | None
    lat_actual: float | None
    lng_actual: float | None

    model_config = ConfigDict(from_attributes=True)


class DomicilioEstadoUpdate(BaseModel):
    estado: EstadoDomicilio
    lat_actual: float | None = Field(default=None, ge=-90, le=90)
    lng_actual: float | None = Field(default=None, ge=-180, le=180)


class HistorialEstadoDomicilioOut(BaseModel):
    estado: EstadoDomicilio
    lat_actual: float | None
    lng_actual: float | None
    registrado_en: datetime

    model_config = ConfigDict(from_attributes=True)

