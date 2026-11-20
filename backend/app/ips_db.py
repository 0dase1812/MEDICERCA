"""Connections to the independent information systems of registered IPSs."""
from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

if TYPE_CHECKING:
    from app.models.ips import InstitucionPrestadora


logger = logging.getLogger(__name__)


class IPSBase(DeclarativeBase):
    """Models stored inside each IPS database, never in the central database."""


_engines: dict[str, object] = {}
_session_factories: dict[str, sessionmaker] = {}


def _connection_key(ips: InstitucionPrestadora) -> str:
    if not ips.activa:
        raise ValueError("La IPS no esta activa")
    if ips.tipo_integracion.value != "base_datos_directa":
        raise ValueError("La IPS no usa una conexion directa de base de datos")
    if not ips.clave_conexion:
        raise ValueError("La IPS no tiene una conexion directa configurada")
    return ips.clave_conexion


def _get_engine_for_key(clave_conexion: str):
    if clave_conexion not in _engines:
        url = settings.database_url_for_ips_connection(clave_conexion)
        # connect_timeout solo existe en PostgreSQL (psycopg2); SQLite (tests) no lo usa.
        argumentos = {"connect_timeout": settings.ips_connect_timeout_segundos} if url.startswith("postgresql") else {}
        _engines[clave_conexion] = create_engine(url, pool_pre_ping=True, connect_args=argumentos)
    return _engines[clave_conexion]


def _get_session_factory(clave_conexion: str) -> sessionmaker:
    if clave_conexion not in _session_factories:
        _session_factories[clave_conexion] = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine_for_key(clave_conexion)
        )
    return _session_factories[clave_conexion]


@contextmanager
def ips_session(ips: InstitucionPrestadora) -> Iterator[Session]:
    """Open and close a session to the independent database of an IPS."""
    db = _get_session_factory(_connection_key(ips))()
    try:
        yield db
    finally:
        db.close()


def crear_tablas_ips_registradas(ips_registradas: Sequence[InstitucionPrestadora]) -> None:
    """Create schemas for direct IPS connections; only used in the local demo."""
    import app.models_ips  # noqa: F401

    for ips in ips_registradas:
        if ips.activa and ips.tipo_integracion.value == "base_datos_directa" and ips.clave_conexion:
            try:
                IPSBase.metadata.create_all(bind=_get_engine_for_key(ips.clave_conexion))
            except Exception:
                # Una IPS caída al arrancar no debe impedir que el resto del sistema levante.
                logger.exception("No se pudo preparar el esquema de la IPS %s", ips.codigo)


def obtener_engine_ips(clave_conexion: str):
    """Acceso público a un engine de IPS (para healthchecks u otras necesidades
    operativas que no deben depender del nombre interno `_get_engine_for_key`)."""
    return _get_engine_for_key(clave_conexion)


def get_engine_para_pruebas(clave_conexion: str):
    """Test-only access to an IPS engine without exposing runtime internals."""
    return _get_engine_for_key(clave_conexion)


def limpiar_conexiones_ips_para_pruebas() -> None:
    _engines.clear()
    _session_factories.clear()
