from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.afiliaciones import exigir_ips_del_usuario, obtener_ips_vigente_usuario
from app.core.deps import get_current_user
from app.database import get_db
from app.ips_db import ips_session
from app.models.medicamento import Medicamento
from app.models.usuario import RolUsuario, Usuario
from app.models_ips import HistoriaClinica, PrescripcionActiva
from app.schemas.historia_clinica import HistoriaClinicaCreate, HistoriaClinicaOut, PrescripcionOut

router = APIRouter(prefix="/api/v1/historia-clinica", tags=["historia-clinica"])


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
    """Version basica (sprint 2): el regente crea o actualiza el diagnostico
    de un paciente de su IPS, y opcionalmente agrega medicamentos formulados.
    No permite todavia editar/retirar una prescripcion existente — queda
    para el sprint 3, con una pantalla dedicada."""
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
        else:
            historia.diagnostico_simulado = payload.diagnostico_simulado
            historia.actualizado_en = datetime.now(timezone.utc)
        db.flush()

        for medicamento_id in payload.medicamento_ids:
            db.add(
                PrescripcionActiva(
                    historia_id=historia.id,
                    medicamento_id=medicamento_id,
                    fecha_formula=date.today(),
                    vigente=True,
                )
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
