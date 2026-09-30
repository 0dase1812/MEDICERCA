from pydantic import BaseModel, ConfigDict

from app.models.medicamento import CondicionVenta


class MedicamentoCreate(BaseModel):
    nombre_generico: str
    nombre_comercial: str
    dosis: str
    presentacion: str
    condicion_venta: CondicionVenta
    control_especial: bool = False
    registro_sanitario: str
    # Ej.: "Tomar 1 tableta cada 8 horas con alimentos".
    indicaciones_uso: str
    # Ej.: "2 cajas" — lo que se entrega físicamente por autorización.
    cantidad_por_entrega: str
    # Cuántos días cubre esa cantidad (p.ej. 30 para "1 mes"); se usa para
    # calcular hasta cuándo es válida una orden ya aprobada.
    duracion_tratamiento_dias: int


class MedicamentoOut(MedicamentoCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
