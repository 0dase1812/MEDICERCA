from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.availability_engine import buscar_disponibilidad
from app.database import get_db
from app.schemas.disponibilidad import ConsultaDisponibilidad, RespuestaDisponibilidad

router = APIRouter(prefix="/api/v1/disponibilidad", tags=["disponibilidad"])


@router.post("", response_model=RespuestaDisponibilidad)
def consultar(payload: ConsultaDisponibilidad, db_central: Session = Depends(get_db)):
    """
    Consulta las 3 IPS simuladas (bases de datos independientes) y agrega
    los resultados: punto más cercano -> otro punto de la ciudad -> otra
    ciudad -> no disponible.
    """
    return buscar_disponibilidad(
        db_central=db_central,
        medicamento_id=payload.medicamento_id,
        lat_usuario=payload.lat_usuario,
        lng_usuario=payload.lng_usuario,
        ciudad_usuario=payload.ciudad_usuario,
    )
