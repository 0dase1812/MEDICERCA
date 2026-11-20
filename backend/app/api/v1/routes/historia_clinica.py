from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.afiliaciones import exigir_ips_del_usuario, obtener_ips_vigente_usuario
from app.core.deps import get_current_user
from app.database import get_db
from app.ips_db import ips_session
from app.models.medicamento import Medicamento
from app.models.usuario import RolUsuario, Usuario
from app.models_ips import HistoriaClinica, HistorialHistoriaClinica, PrescripcionActiva
from app.schemas.historia_clinica import (
    HistoriaClinicaCreate,
    HistoriaClinicaOut,
    HistorialHistoriaClinicaOut,
    PrescripcionOut,
    PrescripcionUpdate,
)

router = APIRouter(prefix="/api/v1/historia-clinica", tags=["historia-clinica"])


def _registrar_auditoria(
    db: Session,
    *,
    historia_id: int,
    entidad: str,
    entidad_id: int | None,
    accion: str,
    valor_anterior: str | None,
    valor_nuevo: str | None,
    autor: str,
) -> None:
    """Escribe una fila de auditoria (HU-S3-02). Nunca edita ni borra una
    fila existente, solo agrega — ver HistorialHistoriaClinica."""
    db.add(
        HistorialHistoriaClinica(
            historia_id=historia_id,
            entidad=entidad,
            entidad_id=entidad_id,
            accion=accion,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            autor=autor,
        )
    )


def _obtener_historia_por_cedula(db: Session, cedula_paciente: str) -> HistoriaClinica:
    """Busca la historia clinica de un paciente, para operaciones de
    escritura/auditoria restringidas al regente de esa IPS. 404 si el
    paciente aun no tiene historia registrada en esta IPS."""
    historia = db.query(HistoriaClinica).filter(HistoriaClinica.cedula == cedula_paciente).first()
    if not historia:
        raise HTTPException(status_code=404, detail="No hay historia clinica para ese paciente en esta IPS")
    return historia


@router.get("/mia", response_model=HistoriaClinicaOut)
def mi_historia_clinica(
    db_central: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)
):
    """Resolves the user's current affiliation then queries that IPS by identity."""
    ips = obtener_ips_vigente_usuario(db_central, usuario)
    with ips_session(ips) as db:
        historia = db.query(HistoriaClinica).filter(HistoriaClinica.cedula == usuario.cedula).first()
        if not historia:
            raise HTTPException(status_code=404, detail="No hay historia clinica para este usuario en su IPS")
        return HistoriaClinicaOut(
            ips_id=ips.id,
            ips_nombre=ips.nombre_ficticio,
            diagnostico_simulado=historia.diagnostico_simulado,
            actualizado_en=historia.actualizado_en,
            prescripciones=[PrescripcionOut.model_validate(p) for p in historia.prescripciones],
        )


@router.post("/{ips_id}", response_model=HistoriaClinicaOut, status_code=201)
def registrar_historia_clinica(
    ips_id: int,
    payload: HistoriaClinicaCreate,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """El regente crea o actualiza el diagnostico de un paciente de su IPS,
    y opcionalmente agrega medicamentos formulados. Editar/retirar una
    prescripcion existente una por una vive en los endpoints dedicados
    PATCH/DELETE .../prescripciones/{id} (sprint 3, HU-S3-01)."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)

    paciente = db_central.query(Usuario).filter(Usuario.cedula == payload.cedula_paciente).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="No existe un paciente con esa cédula")
    if paciente.ips_id != ips_id:
        raise HTTPException(status_code=403, detail="Ese paciente no está afiliado a tu IPS")

    for medicamento_id in payload.medicamento_ids:
        if not db_central.get(Medicamento, medicamento_id):
            raise HTTPException(status_code=404, detail=f"Medicamento {medicamento_id} no encontrado en el catálogo")

    with ips_session(ips) as db:
        historia = db.query(HistoriaClinica).filter(HistoriaClinica.cedula == payload.cedula_paciente).first()
        if historia is None:
            historia = HistoriaClinica(cedula=payload.cedula_paciente, diagnostico_simulado=payload.diagnostico_simulado)
            db.add(historia)
            db.flush()
            _registrar_auditoria(
                db,
                historia_id=historia.id,
                entidad="diagnostico",
                entidad_id=None,
                accion="creacion",
                valor_anterior=None,
                valor_nuevo=payload.diagnostico_simulado,
                autor=usuario.nombre,
            )
        else:
            diagnostico_anterior = historia.diagnostico_simulado
            historia.diagnostico_simulado = payload.diagnostico_simulado
            historia.actualizado_en = datetime.now(timezone.utc)
            if diagnostico_anterior != payload.diagnostico_simulado:
                _registrar_auditoria(
                    db,
                    historia_id=historia.id,
                    entidad="diagnostico",
                    entidad_id=None,
                    accion="edicion",
                    valor_anterior=diagnostico_anterior,
                    valor_nuevo=payload.diagnostico_simulado,
                    autor=usuario.nombre,
                )
        db.flush()

        for medicamento_id in payload.medicamento_ids:
            prescripcion = PrescripcionActiva(
                historia_id=historia.id,
                medicamento_id=medicamento_id,
                fecha_formula=date.today(),
                vigente=True,
            )
            db.add(prescripcion)
            db.flush()
            _registrar_auditoria(
                db,
                historia_id=historia.id,
                entidad="prescripcion",
                entidad_id=prescripcion.id,
                accion="creacion",
                valor_anterior=None,
                valor_nuevo=f"medicamento_id={medicamento_id}, fecha_formula={prescripcion.fecha_formula}",
                autor=usuario.nombre,
            )
        db.commit()
        db.refresh(historia)
        return HistoriaClinicaOut(
            ips_id=ips.id,
            ips_nombre=ips.nombre_ficticio,
            diagnostico_simulado=historia.diagnostico_simulado,
            actualizado_en=historia.actualizado_en,
            prescripciones=[PrescripcionOut.model_validate(p) for p in historia.prescripciones],
        )


@router.patch("/{ips_id}/prescripciones/{prescripcion_id}", response_model=PrescripcionOut)
def editar_prescripcion(
    ips_id: int,
    prescripcion_id: int,
    payload: PrescripcionUpdate,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Sprint 3, HU-S3-01: corrige el medicamento y/o la fecha de una
    prescripcion activa ya registrada, sin tener que retirarla y crear un
    diagnostico nuevo desde cero. Solo aplica sobre una prescripcion
    todavia vigente — una ya retirada se corrige solicitando una nueva."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)

    if payload.medicamento_id is not None and not db_central.get(Medicamento, payload.medicamento_id):
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en el catálogo")

    with ips_session(ips) as db:
        prescripcion = db.get(PrescripcionActiva, prescripcion_id)
        if not prescripcion:
            raise HTTPException(status_code=404, detail="Prescripcion no encontrada en esta IPS")
        if not prescripcion.vigente:
            raise HTTPException(status_code=422, detail="Esta prescripcion ya esta retirada, no se puede editar")

        valor_anterior = f"medicamento_id={prescripcion.medicamento_id}, fecha_formula={prescripcion.fecha_formula}"
        if payload.medicamento_id is not None:
            prescripcion.medicamento_id = payload.medicamento_id
        if payload.fecha_formula is not None:
            prescripcion.fecha_formula = payload.fecha_formula
        valor_nuevo = f"medicamento_id={prescripcion.medicamento_id}, fecha_formula={prescripcion.fecha_formula}"

        _registrar_auditoria(
            db,
            historia_id=prescripcion.historia_id,
            entidad="prescripcion",
            entidad_id=prescripcion.id,
            accion="edicion",
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            autor=usuario.nombre,
        )
        db.commit()
        db.refresh(prescripcion)
        db.expunge(prescripcion)
        return prescripcion


@router.delete("/{ips_id}/prescripciones/{prescripcion_id}", response_model=PrescripcionOut)
def retirar_prescripcion(
    ips_id: int,
    prescripcion_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Sprint 3, HU-S3-01: retira (suspende) una prescripcion activa, sin
    borrarla — queda vigente=False para siempre, como evidencia de que
    alguna vez existio y fue suspendida."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)

    with ips_session(ips) as db:
        prescripcion = db.get(PrescripcionActiva, prescripcion_id)
        if not prescripcion:
            raise HTTPException(status_code=404, detail="Prescripcion no encontrada en esta IPS")
        if not prescripcion.vigente:
            raise HTTPException(status_code=422, detail="Esta prescripcion ya estaba retirada")

        prescripcion.vigente = False
        _registrar_auditoria(
            db,
            historia_id=prescripcion.historia_id,
            entidad="prescripcion",
            entidad_id=prescripcion.id,
            accion="retiro",
            valor_anterior=f"medicamento_id={prescripcion.medicamento_id}, vigente=True",
            valor_nuevo=f"medicamento_id={prescripcion.medicamento_id}, vigente=False",
            autor=usuario.nombre,
        )
        db.commit()
        db.refresh(prescripcion)
        db.expunge(prescripcion)
        return prescripcion


@router.get("/{ips_id}/auditoria/{cedula_paciente}", response_model=list[HistorialHistoriaClinicaOut])
def auditoria_historia_clinica(
    ips_id: int,
    cedula_paciente: str,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Sprint 3, HU-S3-02: linea de tiempo completa de cambios sobre la
    historia clinica de un paciente, para sustentar ante una auditoria que
    cambio, quien lo hizo y cuando. Solo un regente de la IPS del paciente
    puede verla — es informacion operativa, no del paciente mismo (su
    vista de solo lectura es GET /mia, no esta)."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)

    with ips_session(ips) as db:
        historia = _obtener_historia_por_cedula(db, cedula_paciente)
        filas = (
            db.query(HistorialHistoriaClinica)
            .filter(HistorialHistoriaClinica.historia_id == historia.id)
            .order_by(HistorialHistoriaClinica.registrado_en)
            .all()
        )
        for fila in filas:
            db.expunge(fila)
        return filas
