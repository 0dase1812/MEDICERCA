from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PrescripcionOut(BaseModel):
    id: int
    medicamento_id: int
    fecha_formula: date
    vigente: bool

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
