import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.afiliaciones import exigir_ips_del_usuario, obtener_ips_vigente_usuario
from app.core.deps import get_current_user
from app.core.email import enviar_correo
from app.database import get_db
from app.ips_db import ips_session
from app.models.medicamento import Medicamento
from app.models.usuario import RolUsuario, Usuario
from app.models_ips import EstadoOrden, HistorialEstadoOrden, OrdenMedica
from app.schemas.pedido import HistorialEstadoOrdenOut, OrdenMedicaOut

router = APIRouter(prefix="/api/v1/ordenes", tags=["ordenes"])

# La fórmula se sube como archivo (no como link a otro sitio), así que se
# valida tipo y tamaño acá — sin esto, cualquiera podría subir un ejecutable
# o un archivo de varios GB directo a la base de datos.
TIPOS_ARCHIVO_PERMITIDOS = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("", response_model=OrdenMedicaOut, status_code=201)
async def cargar_orden(
    ips_id: int = Form(...),
    medicamento_id: int = Form(...),
    archivo: UploadFile = File(..., description="Foto o PDF de la fórmula médica"),
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Carga una formula solamente en la IPS vigente del paciente.

    El archivo llega como multipart/form-data (no como URL externa): se
    valida tipo/tamaño y se guarda codificado en base64 ("data URI"), listo
    para mostrarse o descargarse directo desde el navegador sin depender de
    ningún almacenamiento externo.
    """
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)
    if not db_central.get(Medicamento, medicamento_id):
        raise HTTPException(status_code=404, detail="Medicamento no encontrado en el catalogo")

    if archivo.content_type not in TIPOS_ARCHIVO_PERMITIDOS:
        raise HTTPException(
            status_code=422,
            detail="Formato no soportado. Sube una imagen (JPG, PNG, WEBP) o un PDF.",
        )
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(status_code=413, detail="El archivo no puede superar 5 MB.")

    data_uri = f"data:{archivo.content_type};base64,{base64.b64encode(contenido).decode()}"

    with ips_session(ips) as db:
        orden = OrdenMedica(
            usuario_cedula=usuario.cedula,
            archivo_url=data_uri,
            medicamento_id=medicamento_id,
            estado=EstadoOrden.PENDIENTE,
        )
        db.add(orden)
        db.flush()
        # Primer registro del historial, igual que con los domicilios: así la
        # trazabilidad siempre arranca completa desde la carga, sin huecos.
        db.add(HistorialEstadoOrden(orden_id=orden.id, estado=orden.estado))
        db.commit()
        db.refresh(orden)
        db.expunge(orden)
        return orden


@router.get("/mias", response_model=list[OrdenMedicaOut])
def mis_ordenes(
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Ordenes cargadas por el usuario autenticado en su IPS vigente, mas
    recientes primero. Sin este endpoint, la unica forma de conocer el
    estado de una orden ya creada era recordar su id manualmente."""
    ips = obtener_ips_vigente_usuario(db_central, usuario)
    with ips_session(ips) as db:
        ordenes = (
            db.query(OrdenMedica)
            .filter(OrdenMedica.usuario_cedula == usuario.cedula)
            .order_by(OrdenMedica.creado_en.desc())
            .all()
        )
        for orden in ordenes:
            db.expunge(orden)
        return ordenes


@router.get("/pendientes", response_model=list[OrdenMedicaOut])
def ordenes_pendientes(
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Cola de ordenes PENDIENTE en la IPS vigente del regente, para que
    pueda aprobar/rechazar sin depender de que el paciente le pase el id
    de la orden por otro medio."""
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    ips = obtener_ips_vigente_usuario(db_central, usuario)
    with ips_session(ips) as db:
        ordenes = (
            db.query(OrdenMedica)
            .filter(OrdenMedica.estado == EstadoOrden.PENDIENTE)
            .order_by(OrdenMedica.creado_en)
            .all()
        )
        for orden in ordenes:
            db.expunge(orden)
        return ordenes


@router.get("/{ips_id}/{orden_id}", response_model=OrdenMedicaOut)
def obtener_orden(
    ips_id: int,
    orden_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Mismo control de acceso que GET /domicilios/{ips_id}/{domicilio_id}:
    el paciente dueño de la orden, o un regente de esa misma IPS."""
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        orden = db.get(OrdenMedica, orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        if usuario.rol != RolUsuario.REGENTE and orden.usuario_cedula != usuario.cedula:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta orden")
        db.expunge(orden)
        return orden


@router.get("/{ips_id}/{orden_id}/historial", response_model=list[HistorialEstadoOrdenOut])
def obtener_historial_orden(
    ips_id: int,
    orden_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Línea de tiempo completa de la revisión de una orden (cargada ->
    aprobada/rechazada), con quién la revisó y cuándo. Mismo control de
    acceso que su endpoint hermano GET /{ips_id}/{orden_id}."""
    ips = exigir_ips_del_usuario(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        orden = db.get(OrdenMedica, orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        if usuario.rol != RolUsuario.REGENTE and orden.usuario_cedula != usuario.cedula:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta orden")
        filas = (
            db.query(HistorialEstadoOrden)
            .filter(HistorialEstadoOrden.orden_id == orden_id)
            .order_by(HistorialEstadoOrden.registrado_en)
            .all()
        )
        for fila in filas:
            db.expunge(fila)
        return filas


@router.post("/{ips_id}/{orden_id}/aprobar", response_model=OrdenMedicaOut)
def aprobar_orden(
    ips_id: int,
    orden_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    ips = _validar_regente_de_su_ips(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        orden = db.get(OrdenMedica, orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        orden.estado = EstadoOrden.APROBADA
        orden.revisado_por = usuario.nombre
        orden.aprobado_en = datetime.now(timezone.utc)
        db.add(HistorialEstadoOrden(orden_id=orden.id, estado=orden.estado, revisado_por=usuario.nombre))
        db.commit()
        db.refresh(orden)
        db.expunge(orden)
    _notificar_cambio_orden(db_central, orden, "Tu orden médica fue aprobada")
    return orden


@router.post("/{ips_id}/{orden_id}/rechazar", response_model=OrdenMedicaOut)
def rechazar_orden(
    ips_id: int,
    orden_id: int,
    db_central: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    ips = _validar_regente_de_su_ips(db_central, usuario, ips_id)
    with ips_session(ips) as db:
        orden = db.get(OrdenMedica, orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        orden.estado = EstadoOrden.RECHAZADA
        orden.revisado_por = usuario.nombre
        db.add(HistorialEstadoOrden(orden_id=orden.id, estado=orden.estado, revisado_por=usuario.nombre))
        db.commit()
        db.refresh(orden)
        db.expunge(orden)
    _notificar_cambio_orden(db_central, orden, "Tu orden médica fue rechazada")
    return orden


def _validar_regente_de_su_ips(db_central: Session, usuario: Usuario, ips_id: int):
    if usuario.rol != RolUsuario.REGENTE:
        raise HTTPException(status_code=403, detail="Esta accion requiere rol de regente")
    return exigir_ips_del_usuario(db_central, usuario, ips_id)


def _notificar_cambio_orden(db_central: Session, orden: OrdenMedica, asunto: str) -> None:
    paciente = db_central.query(Usuario).filter(Usuario.cedula == orden.usuario_cedula).first()
    if not paciente:
        return
    enviar_correo(
        paciente.correo,
        asunto,
        f"<p>Hola {paciente.nombre},</p><p>{asunto} (orden #{orden.id}).</p>",
    )
