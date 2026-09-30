"""Shared pytest infrastructure using four temporary SQLite databases."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="medicerca-pytest-"))


def _sqlite_url(name: str) -> str:
    return f"sqlite:///{(_TEST_DB_DIR / name).as_posix()}?check_same_thread=False"


# PNG válido mínimo (1x1 transparente), para probar POST /api/v1/ordenes
# ahora que recibe un archivo real (multipart/form-data) en vez de una URL.
ARCHIVO_PRUEBA_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def archivo_formula_prueba(nombre: str = "formula.png", content_type: str = "image/png"):
    """Dict listo para pasarle a TestClient como `files=` al cargar una orden."""
    return {"archivo": (nombre, ARCHIVO_PRUEBA_PNG, content_type)}


# Must be defined before importing any app module.
os.environ["DATABASE_URL"] = _sqlite_url("central.sqlite3")
os.environ["DATABASE_URL_IPS_1"] = _sqlite_url("ips_1.sqlite3")
os.environ["DATABASE_URL_IPS_2"] = _sqlite_url("ips_2.sqlite3")
os.environ["DATABASE_URL_IPS_3"] = _sqlite_url("ips_3.sqlite3")
os.environ["SECRET_KEY"] = "clave-exclusiva-para-pruebas"
os.environ["EMAIL_MODO"] = "simulado"
os.environ["AUTO_CREATE_SCHEMA"] = "false"

import app.models  # noqa: E402, F401
import app.models_ips  # noqa: E402, F401
from app.core.afiliaciones import cambiar_afiliacion  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.ips_db import IPSBase, get_engine_para_pruebas, ips_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ips import InstitucionPrestadora, TipoIntegracionIPS  # noqa: E402
from app.models.usuario import RolUsuario, Usuario  # noqa: E402


def _crear_ips_demo(db: Any) -> list[InstitucionPrestadora]:
    configuracion = [
        (1, "IPS-VITALIS", "IPS Vitalis Central", "demo_ips_1"),
        (2, "IPS-SOMOS", "IPS Somos Salud", "demo_ips_2"),
        (3, "IPS-RED", "IPS Red Continuo", "demo_ips_3"),
    ]
    ips = [
        InstitucionPrestadora(
            id=identificador,
            codigo=codigo,
            nombre_ficticio=nombre,
            clave_conexion=clave,
            tipo_integracion=TipoIntegracionIPS.BASE_DATOS_DIRECTA,
        )
        for identificador, codigo, nombre, clave in configuracion
    ]
    db.add_all(ips)
    db.commit()
    return ips


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """El Limiter de slowapi guarda su estado en memoria a nivel de proceso,
    fuera del ciclo de vida de `client`/`reset_databases`. Sin este reset,
    los contadores se acumulan ENTRE tests (todos comparten la misma IP
    simulada del TestClient) y un test que corre tarde en la suite podria
    fallar con 429 por peticiones de tests anteriores, no por las suyas."""
    from app.core.rate_limit import limiter

    limiter.reset()


@pytest.fixture(autouse=True)
def reset_databases() -> Iterator[None]:
    """Recreate central data plus the three registered demo IPS systems."""
    Base.metadata.drop_all(bind=engine)
    for clave in ("demo_ips_1", "demo_ips_2", "demo_ips_3"):
        IPSBase.metadata.drop_all(bind=get_engine_para_pruebas(clave))
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _crear_ips_demo(db)
    finally:
        db.close()
    for clave in ("demo_ips_1", "demo_ips_2", "demo_ips_3"):
        IPSBase.metadata.create_all(bind=get_engine_para_pruebas(clave))
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Iterator[Any]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def usuario_factory() -> Callable[..., dict[str, Any]]:
    """Provision verified users for protected scenarios, including affiliation."""
    contador = 0

    def crear_usuario(
        *,
        nombre: str = "Paciente de prueba",
        cedula: str | None = None,
        correo: str | None = None,
        password: str = "ClaveSegura123",
        rol: RolUsuario = RolUsuario.PACIENTE,
        ips_id: int | None = 1,
        verificado: bool = True,
    ) -> dict[str, Any]:
        nonlocal contador
        contador += 1
        sufijo = str(contador)
        usuario = Usuario(
            nombre=nombre,
            cedula=cedula or f"10000000{sufijo}",
            correo=correo or f"usuario{sufijo}@prueba.com",
            password_hash=hash_password(password),
            rol=rol,
            ips_id=ips_id,
            verificado=verificado,
        )
        db = SessionLocal()
        try:
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
            if ips_id is not None:
                ips = db.get(InstitucionPrestadora, ips_id)
                assert ips is not None
                cambiar_afiliacion(db, usuario, ips)
                db.commit()
            return {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "cedula": usuario.cedula,
                "correo": usuario.correo,
                "password": password,
                "rol": usuario.rol,
                "ips_id": usuario.ips_id,
            }
        finally:
            db.close()

    return crear_usuario


@pytest.fixture
def token_factory(client: TestClient, usuario_factory: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, str]]:
    def crear_token(**kwargs: Any) -> dict[str, str]:
        usuario = usuario_factory(**kwargs)
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": usuario["correo"], "password": usuario["password"]},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return crear_token


@pytest.fixture
def ips_db() -> Callable[[int], Any]:
    @contextmanager
    def abrir_ips(ips_id: int):
        db_central = SessionLocal()
        try:
            ips = db_central.get(InstitucionPrestadora, ips_id)
            assert ips is not None
            with ips_session(ips) as db_ips:
                yield db_ips
        finally:
            db_central.close()

    return abrir_ips
