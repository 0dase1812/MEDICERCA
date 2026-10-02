from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.core.afiliaciones import cambiar_afiliacion, obtener_ips_activa
from app.core.captcha import CaptchaInvalido, verificar_captcha
from app.core.deps import get_current_user, security_scheme
from app.core.email import enviar_correo
from app.core.otp import generar_codigo, validar_codigo
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password_tiempo_constante,
)
from app.database import get_db
from app.models.codigo_verificacion import PropositoCodigo
from app.models.token_revocado import TokenRevocado
from app.models.usuario import RolUsuario, Usuario
from app.schemas.usuario import (
    ConfirmarCambioPasswordRequest,
    LoginRequest,
    RegistroOut,
    SolicitarCambioPasswordOut,
    SolicitarCambioPasswordRequest,
    Token,
    UsuarioCreate,
    UsuarioOut,
    VerificarCodigoRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Sin este límite, alguien puede probar contraseñas contra un correo conocido
# indefinidamente. 5 intentos + 15 minutos de bloqueo es suficientemente
# molesto para un ataque automatizado sin ser desproporcionado para un
# usuario real que se equivocó escribiendo su clave.
MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN_MINUTOS = 15


def _codigo_demo(codigo: str) -> str | None:
    """En modo 'simulado' el código va en la respuesta; en modo 'real' no se expone."""
    return codigo if settings.email_modo == "simulado" else None


@router.post("/register", response_model=RegistroOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def registrar(request: Request, payload: UsuarioCreate, db: Session = Depends(get_db)):
    try:
        verificar_captcha(payload.captcha_token)
    except CaptchaInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    existe = db.query(Usuario).filter(Usuario.correo == payload.correo).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    existe_cedula = db.query(Usuario).filter(Usuario.cedula == payload.cedula).first()
    if existe_cedula:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cédula")

    ips = obtener_ips_activa(db, payload.ips_id) if payload.ips_id is not None else None

    usuario = Usuario(
        nombre=payload.nombre,
        cedula=payload.cedula,
        correo=payload.correo,
        password_hash=hash_password(payload.password),
        eps_id=payload.eps_id,
        ips_id=payload.ips_id,
        rol=RolUsuario.PACIENTE,
        verificado=False,
    )
    db.add(usuario)
    db.flush()
    db.refresh(usuario)

    if ips is not None:
        cambiar_afiliacion(db, usuario, ips)
    db.commit()
    db.refresh(usuario)

    codigo = generar_codigo(db, correo=usuario.correo, proposito=PropositoCodigo.REGISTRO)
    enviar_correo(
        usuario.correo,
        "Confirma tu cuenta en MediCerca",
        f"<p>Hola {usuario.nombre},</p><p>Tu código de verificación es: <strong>{codigo}</strong></p>",
    )

    return RegistroOut(
        usuario=usuario,
        mensaje="Cuenta creada. Confirma tu correo con el código de verificación para poder iniciar sesión.",
        codigo_demo=_codigo_demo(codigo),
    )


@router.post("/verificar-registro", response_model=UsuarioOut)
@limiter.limit("20/minute")
def verificar_registro(request: Request, payload: VerificarCodigoRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == payload.correo).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    valido = validar_codigo(db, correo=payload.correo, codigo=payload.codigo, proposito=PropositoCodigo.REGISTRO)
    if not valido:
        raise HTTPException(status_code=400, detail="Código inválido o vencido")

    usuario.verificado = True
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        verificar_captcha(payload.captcha_token)
    except CaptchaInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    usuario = db.query(Usuario).filter(Usuario.correo == payload.correo).first()

    ahora = datetime.now(timezone.utc)
    if usuario and usuario.bloqueado_hasta is not None:
        bloqueado_hasta = usuario.bloqueado_hasta.replace(tzinfo=timezone.utc)
        if bloqueado_hasta > ahora:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos fallidos. Intenta de nuevo en unos minutos.",
            )

    # Ojo con el short-circuit de "or": si escribiéramos
    # `not usuario or not verify_...(...)`, Python nunca llamaría a
    # verify_password_tiempo_constante cuando usuario es None (porque
    # `not usuario` ya sería True), y volveríamos a tener el timing leak que
    # esta función existe para evitar. Por eso se calcula aparte, siempre.
    password_hash = usuario.password_hash if usuario else None
    password_valida = verify_password_tiempo_constante(payload.password, password_hash)
    if not usuario or not password_valida:
        if usuario:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= MAX_INTENTOS_LOGIN:
                usuario.bloqueado_hasta = ahora + timedelta(minutes=BLOQUEO_LOGIN_MINUTOS)
            db.commit()
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    if not usuario.verificado:
        raise HTTPException(status_code=403, detail="Debes verificar tu correo antes de iniciar sesión")

    if usuario.intentos_fallidos or usuario.bloqueado_hasta:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.commit()

    token = create_access_token(subject=usuario.correo)
    return Token(access_token=token)


@router.post("/solicitar-cambio-password", response_model=SolicitarCambioPasswordOut)
@limiter.limit("5/minute")
def solicitar_cambio_password(request: Request, payload: SolicitarCambioPasswordRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == payload.correo).first()
    if not usuario:
        # No revelamos si el correo existe o no, por seguridad — mismo mensaje en ambos casos.
        return SolicitarCambioPasswordOut(mensaje="Si el correo existe, se envió un código de verificación.")

    codigo = generar_codigo(db, correo=payload.correo, proposito=PropositoCodigo.CAMBIO_PASSWORD)
    enviar_correo(
        usuario.correo,
        "Código para cambiar tu contraseña en MediCerca",
        f"<p>Tu código para cambiar la contraseña es: <strong>{codigo}</strong></p>"
        "<p>Si no fuiste tú quien lo solicitó, ignora este correo.</p>",
    )
    return SolicitarCambioPasswordOut(
        mensaje="Si el correo existe, se envió un código de verificación.",
        codigo_demo=_codigo_demo(codigo),
    )


@router.post("/confirmar-cambio-password", response_model=UsuarioOut)
@limiter.limit("10/minute")
def confirmar_cambio_password(request: Request, payload: ConfirmarCambioPasswordRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == payload.correo).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    valido = validar_codigo(
        db, correo=payload.correo, codigo=payload.codigo, proposito=PropositoCodigo.CAMBIO_PASSWORD
    )
    if not valido:
        raise HTTPException(status_code=400, detail="Código inválido o vencido")

    usuario.password_hash = hash_password(payload.nueva_password)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/me", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(get_current_user)):
    """Identidad del usuario autenticado (rol, ips_id, etc.). El JWT solo
    guarda 'sub' (correo), así que sin este endpoint un cliente no tiene
    forma de saber, tras iniciar sesión, si el usuario es paciente o
    regente ni a qué IPS está afiliado."""
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credenciales: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
):
    """Revoca el token actual: no invalida otras sesiones del mismo usuario, solo
    este token puntual (identificado por su 'jti'). Idempotente — si el token ya
    es inválido o ya estaba revocado, igual responde 204."""
    token = credenciales.credentials
    payload = decode_access_token(token)
    if payload is None:
        return

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return

    # Limpieza oportunista: no necesitamos guardar tokens cuyo 'exp' ya pasó,
    # porque decode_access_token ya los rechaza por sí solo.
    db.query(TokenRevocado).filter(TokenRevocado.expira_en < datetime.now(timezone.utc)).delete()

    if db.get(TokenRevocado, jti) is None:
        db.add(TokenRevocado(jti=jti, expira_en=datetime.fromtimestamp(exp, tz=timezone.utc)))
    db.commit()
    