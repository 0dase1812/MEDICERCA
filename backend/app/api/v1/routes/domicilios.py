from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.afiliaciones import exigir_ips_del_usuario, obtener_ips_vigente_usuario
from app.core.deps import get_current_user
from app.core.email import enviar_correo
from app.core.legal_rules import MedicamentoNoElegibleParaDomicilio, validar_domicilio_o_falla
from app.database import get_db
from app.ips_db import ips_session
from app.models.medicamento import Medicamento
from app.models.usuario import RolUsuario, Usuario
from app.models_ips import Domicilio, EstadoDomicilio, EstadoOrden, HistorialEstadoDomicilio, OrdenMedica, PuntoVenta
from app.schemas.pedido import DomicilioCreate, DomicilioEstadoUpdate, DomicilioOut, HistorialEstadoDomicilioOut

router = APIRouter(prefix="/api/v1/domicilios", tags=["domicilios"])


def _obtener_domicilio_del_usuario(db_central: Session, usuario: Usuario, ips_id: int, domicilio_id: int):
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        domicilio = db.get(Domicilio, domicilio_id)
        if not domicilio:
            raise HTTPException(status_code=404, detail="Domicilio no encontrado")
        orden = db.get(OrdenMedica, domicilio.orden_id)
        if not orden or orden.usuario_cedula != usuario.cedula:
            raise HTTPException(status_code=403, detail="No tienes acceso a este domicilio")
        db.expunge(domicilio)
        return ips, domicilio


@router.post("", response_model=DomicilioOut, status_code=201)
def crear_domicilio(
    payload: DomicilioCreate,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    ips = exigir_ips_del_usuario(db_central, usuario, payload.ips_id)
    medicamento = db_central.get(Medicamento, payload.medicamento_id)
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en el catalogo")

    with ips_session(ips) as db:
        orden = db.get(OrdenMedica, payload.orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden medica no encontrada en esa IPS")
        if orden.usuario_cedula != usuario.cedula:
            raise HTTPException(status_code=403, detail="No puedes usar una orden medica de otro paciente")
        if orden.medicamento_id != payload.medicamento_id:
            # Sin esta validación, una orden aprobada para CUALQUIER medicamento RX
            # serviría para pedir a domicilio otro distinto al que el médico formuló.
            raise HTTPException(
                status_code=422,
                detail="El medicamento solicitado no coincide con el amparado por esta orden médica",
            )
        if not db.get(PuntoVenta, payload.punto_origen_id):
            raise HTTPException(status_code=404, detail="Punto de origen no encontrado en esa IPS")
        # Una orden aprobada ampara UNA sola entrega: sin este chequeo, el
        # mismo paciente podria pedir el mismo medicamento a domicilio
        # varias veces reusando la misma orden ya aprobada. Un domicilio
        # CANCELADO no cuenta: si el paciente lo cancelo, la orden queda
        # libre para pedirlo de nuevo.
        ya_tiene_domicilio = (
            db.query(Domicilio)
            .filter(Domicilio.orden_id == orden.id, Domicilio.estado != EstadoDomicilio.CANCELADO)
            .first()
        )
        if ya_tiene_domicilio:
            raise HTTPException(
                status_code=422,
                detail="Esta orden médica ya tiene un domicilio asociado.",
            )
        try:
            validar_domicilio_o_falla(medicamento, orden.estado == EstadoOrden.APROBADA)
        except MedicamentoNoElegibleParaDomicilio as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        domicilio = Domicilio(orden_id=orden.id, punto_origen_id=payload.punto_origen_id)
        db.add(domicilio)
        db.flush()
        # Primer registro del historial: el estado inicial con el que nace todo
        # domicilio (CONFIRMADO). Así el historial siempre arranca completo,
        # sin un "hueco" antes del primer cambio manual.
        db.add(HistorialEstadoDomicilio(domicilio_id=domicilio.id, estado=domicilio.estado))
        db.commit()
        db.refresh(domicilio)
        db.expunge(domicilio)
        return domicilio


@router.get("/mias", response_model=list[DomicilioOut])
def mis_domicilios(
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Domicilios del usuario autenticado en su IPS vigente, mas recientes
    primero. Sin esto, el unico modo de conocer un domicilio era recordar
    a mano el id que devolvio POST /domicilios al crearlo."""
    ips = obtener_ips_vigente_usuario(db_central, usuario)
    with ips_session(ips) as db:
        domicilios = (
            db.query(Domicilio)
            .join(OrdenMedica, Domicilio.orden_id == OrdenMedica.id)
            .filter(OrdenMedica.usuario_cedula == usuario.cedula)
            .order_by(Domicilio.id.desc())
            .all()
        )
        for domicilio in domicilios:
            db.expunge(domicilio)
        return domicilios


@router.get("/activos", response_model=list[DomicilioOut])
def domicilios_activos(
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Domicilios sin entregar en la IPS vigente del regente, para que
    tenga una cola de trabajo sin depender de que el paciente le comparta
    el id del domicilio por otro medio."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = obtener_ips_vigente_usuario(db_central, usuario)
    with ips_session(ips) as db:
        domicilios = (
            db.query(Domicilio)
            .filter(Domicilio.estado.notin_([EstadoDomicilio.ENTREGADO, EstadoDomicilio.CANCELADO]))
            .order_by(Domicilio.id)
            .all()
        )
        for domicilio in domicilios:
            db.expunge(domicilio)
        return domicilios


@router.get("/{ips_id}/{domicilio_id}", response_model=DomicilioOut)
def obtener(
    ips_id: int,
    domicilio_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    _, domicilio = _obtener_domicilio_del_usuario(db_central, usuario, ips_id, domicilio_id)
    return domicilio


@router.get("/{ips_id}/{domicilio_id}/historial", response_model=list[HistorialEstadoDomicilioOut])
def obtener_historial(
    ips_id: int,
    domicilio_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Linea de tiempo completa de un domicilio, en orden cronologico. Mismo
    control de acceso que GET /{ips_id}/{domicilio_id} (reutiliza el mismo
    helper): solo el paciente dueño del pedido puede verlo, sin excepcion de
    rol — igual que su endpoint hermano."""
    ips, _ = _obtener_domicilio_del_usuario(db_central, usuario, ips_id, domicilio_id)
    with ips_session(ips) as db:
        filas = (
            db.query(HistorialEstadoDomicilio)
            .filter(HistorialEstadoDomicilio.domicilio_id == domicilio_id)
            .order_by(HistorialEstadoDomicilio.registrado_en)
            .all()
        )
        for fila in filas:
            db.expunge(fila)
        return filas


@router.post("/{ips_id}/{domicilio_id}/cancelar", response_model=DomicilioOut)
def cancelar(
    ips_id: int,
    domicilio_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """El paciente dueño del pedido puede cancelarlo mientras todavía no
    salió en camino. Una vez en camino o entregado, ya no tiene sentido
    (el punto de venta ya alistó o despachó el medicamento)."""
    ips, _ = _obtener_domicilio_del_usuario(db_central, usuario, ips_id, domicilio_id)
    with ips_session(ips) as db:
        domicilio = db.get(Domicilio, domicilio_id)
        if domicilio.estado in (EstadoDomicilio.EN_CAMINO, EstadoDomicilio.ENTREGADO, EstadoDomicilio.CANCELADO):
            raise HTTPException(
                status_code=422,
                detail="Este domicilio ya no se puede cancelar (ya salió en camino, fue entregado o ya estaba cancelado).",
            )
        domicilio.estado = EstadoDomicilio.CANCELADO
        db.add(HistorialEstadoDomicilio(domicilio_id=domicilio.id, estado=domicilio.estado))
        db.commit()
        db.refresh(domicilio)
        db.expunge(domicilio)
        return domicilio


@router.patch("/{ips_id}/{domicilio_id}/estado", response_model=DomicilioOut)
def actualizar_estado(
    ips_id: int,
    domicilio_id: int,
    payload: DomicilioEstadoUpdate,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Only the IPS staff can update logistics; patients can only read their tracking."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Solo un regente puede actualizar el estado del domicilio")
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        domicilio = db.get(Domicilio, domicilio_id)
        if not domicilio:
            raise HTTPException(status_code=404, detail="Domicilio no encontrado")
        domicilio.estado = payload.estado
        if payload.lat_actual is not None:
            domicilio.lat_actual = payload.lat_actual
        if payload.lng_actual is not None:
            domicilio.lng_actual = payload.lng_actual
        # Cada cambio de estado queda como una fila nueva, nunca se sobrescribe
        # ni se borra una anterior — así se puede reconstruir la línea de
        # tiempo completa del pedido más adelante.
        db.add(
            HistorialEstadoDomicilio(
                domicilio_id=domicilio.id,
                estado=domicilio.estado,
                lat_actual=domicilio.lat_actual,
                lng_actual=domicilio.lng_actual,
            )
        )
        db.commit()
        db.refresh(domicilio)
        db.expunge(domicilio)
        orden = db.get(OrdenMedica, domicilio.orden_id)
        cedula_paciente = orden.usuario_cedula if orden else None
    if cedula_paciente:
        _notificar_cambio_domicilio(db_central, cedula_paciente, domicilio)
    return domicilio


def _notificar_cambio_domicilio(db_central: Session, cedula_paciente: str, domicilio: Domicilio) -> None:
    paciente = db_central.query(Usuario).filter(Usuario.cedula == cedula_paciente).first()
    if not paciente:
        return
    etiquetas = {
        EstadoDomicilio.EN_ALISTAMIENTO: "está en alistamiento",
        EstadoDomicilio.EN_CAMINO: "ya está en camino",
        EstadoDomicilio.ENTREGADO: "fue entregado",
    }
    descripcion = etiquetas.get(domicilio.estado)
    if not descripcion:
        return
    enviar_correo(
        paciente.correo,
        "Actualización de tu domicilio en MediCerca",
        f"<p>Hola {paciente.nombre},</p><p>Tu domicilio #{domicilio.id} {descripcion}.</p>",
    )
