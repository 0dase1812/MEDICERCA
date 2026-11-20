from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import requerir_regente
from app.database import get_db
from app.models.medicamento import Medicamento
from app.models.usuario import Usuario
from app.schemas.medicamento import MedicamentoCreate, MedicamentoOut
from app.schemas.pagina import Pagina

router = APIRouter(prefix="/api/v1/medicamentos", tags=["medicamentos"])


@router.get("", response_model=Pagina[MedicamentoOut])
def listar(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(
        None,
        min_length=1,
        description="Busca por coincidencia parcial (sin distinguir mayusculas/minusculas) en el "
        "nombre generico o el nombre comercial. No distingue tildes.",
    ),
):
    """Catálogo público (nacional/INVIMA): no requiere login.

    Paginado por `skip`/`limit` en vez de devolver la tabla completa: con
    datos demo no importa, pero un catálogo real (INVIMA) puede tener miles
    de registros.

    Sprint 3 (HU-S3-04): `q` filtra por nombre antes de paginar, para que el
    paciente no tenga que recorrer paginas ordenadas solo por id buscando un
    medicamento puntual."""
    consulta = db.query(Medicamento)
    if q:
        patron = f"%{q}%"
        consulta = consulta.filter(
            or_(Medicamento.nombre_generico.ilike(patron), Medicamento.nombre_comercial.ilike(patron))
        )
    total = consulta.count()
    registros = consulta.order_by(Medicamento.id).offset(skip).limit(limit).all()
    return Pagina(items=registros, total=total, skip=skip, limit=limit)


@router.get("/{medicamento_id}", response_model=MedicamentoOut)
def obtener(medicamento_id: int, db: Session = Depends(get_db)):
    medicamento = db.get(Medicamento, medicamento_id)
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    return medicamento


@router.post("", response_model=MedicamentoOut, status_code=201)
def crear(
    payload: MedicamentoCreate,
    db: Session = Depends(get_db),
    _regente: Usuario = Depends(requerir_regente),  # solo regentes administran el catálogo
):
    medicamento = Medicamento(**payload.model_dump())
    db.add(medicamento)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un medicamento con el registro sanitario {payload.registro_sanitario!r}.",
        )
    db.refresh(medicamento)
    return medicamento
