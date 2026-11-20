from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PrescripcionOut(BaseModel):
    id: int
    medicamento_id: int
    fecha_formula: date
    vigente: bool

    model_config = ConfigDict(from_attributes=True)


class PrescripcionUpdate(BaseModel):
    """Sprint 3 (HU-S3-01): edicion parcial de una prescripcion activa ya
    registrada. Ambos campos son opcionales para permitir corregir solo el
    que tenga el error de digitacion, sin tener que reenviar el otro."""
    medicamento_id: int | None = None
    fecha_formula: date | None = None


class HistorialHistoriaClinicaOut(BaseModel):
    """Sprint 3 (HU-S3-02): una fila del registro de auditoria, de solo lectura."""
    entidad: str
    entidad_id: int | None
    accion: str
    valor_anterior: str | None
    valor_nuevo: str | None
    autor: str
    registrado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class HistoriaClinicaOut(BaseModel):
    ips_id: int
    ips_nombre: str
    diagnostico_simulado: str
    actualizado_en: datetime
    prescripciones: list[PrescripcionOut]


class HistoriaClinicaCreate(BaseModel):
    """Version basica: el regente registra/actualiza el diagnostico de un
    paciente de su IPS y, opcionalmente, los medicamentos que le formula.
    Pendiente para el sprint 3: editar/retirar prescripciones existentes
    una por una, en vez de solo poder agregar nuevas."""
    cedula_paciente: str
    diagnostico_simulado: str
    medicamento_ids: list[int] = []
