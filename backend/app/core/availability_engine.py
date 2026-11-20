"""Interoperability gateway: aggregate availability from registered IPS systems."""
import logging
import math
import unicodedata
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.ips_db import ips_session
from app.models.ips import InstitucionPrestadora
from app.models_ips import Inventario, PuntoVenta
from app.schemas.disponibilidad import IPSNoDisponible, RespuestaDisponibilidad, ResultadoDisponibilidad

logger = logging.getLogger(__name__)


class CalculadorDistancia(ABC):
    """Contrato para calcular la distancia entre el usuario y un punto de venta.

    Hoy solo existe `DistanciaLineaRecta` (fórmula de Haversine, sin llamadas
    externas). El día que se integre una API real de mapas (ej. Google Maps
    Distance Matrix, para distancia/tiempo por calles en vez de línea recta),
    esa integración se escribe como OTRA clase que cumpla este mismo contrato
    — se cambia una línea en `buscar_disponibilidad` (qué calculador usar) y
    el resto del motor no se toca."""

    @abstractmethod
    def distancia_km(self, lat_usuario: float, lng_usuario: float, lat_punto: float, lng_punto: float) -> float:
        raise NotImplementedError


class DistanciaLineaRecta(CalculadorDistancia):
    """Distancia geográfica en línea recta (fórmula de Haversine). No conoce
    calles, tráfico ni rutas reales — es una aproximación intencional para la
    entrega actual, suficiente para ordenar puntos por cercanía relativa."""

    RADIO_TIERRA_KM = 6371.0

    def distancia_km(self, lat_usuario: float, lng_usuario: float, lat_punto: float, lng_punto: float) -> float:
        dlat = math.radians(lat_punto - lat_usuario)
        dlng = math.radians(lng_punto - lng_usuario)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat_usuario)) * math.cos(math.radians(lat_punto)) * math.sin(dlng / 2) ** 2
        )
        return self.RADIO_TIERRA_KM * 2 * math.asin(math.sqrt(a))


# Calculador usado por defecto en toda la app. Cambiar esta única línea (por
# una instancia de un futuro `DistanciaGoogleMaps`, por ejemplo) es todo lo
# que haría falta para pasar a distancia/tiempo real por calles.
calculador_distancia_por_defecto: CalculadorDistancia = DistanciaLineaRecta()


def _normalizar_ciudad(texto: str) -> str:
    """Minúsculas y sin tildes: sin esto, un usuario que escribe 'Bogotá' (con
    tilde, como se escribe realmente) nunca coincide con el 'Bogota' sembrado
    en la demo, y CADA resultado en su propia ciudad cae por error en el nivel
    'otra_ciudad' en vez de 'punto_mas_cercano'/'otro_punto_ciudad'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.strip().lower()


def _consultar_una_ips(ips: InstitucionPrestadora, medicamento_id: int) -> list[tuple[Inventario, PuntoVenta]]:
    with ips_session(ips) as db:
        filas = (
            db.query(Inventario, PuntoVenta)
            .join(PuntoVenta, Inventario.punto_id == PuntoVenta.id)
            .filter(Inventario.medicamento_id == medicamento_id)
            .all()
        )
        for inventario, punto in filas:
            db.expunge(inventario)
            db.expunge(punto)
        return filas


def buscar_disponibilidad(
    db_central: Session,
    medicamento_id: int,
    lat_usuario: float,
    lng_usuario: float,
    ciudad_usuario: str,
    calculador: CalculadorDistancia = calculador_distancia_por_defecto,
) -> RespuestaDisponibilidad:
    ips_activas = db_central.query(InstitucionPrestadora).filter(InstitucionPrestadora.activa.is_(True)).all()
    todas: list[tuple[InstitucionPrestadora, Inventario, PuntoVenta]] = []
    no_disponibles: list[IPSNoDisponible] = []
    for ips in ips_activas:
        if ips.tipo_integracion.value != "base_datos_directa" or not ips.clave_conexion:
            continue
        # Aislamiento de fallas: si UNA IPS no responde, las demás siguen aportando resultados.
        try:
            filas = _consultar_una_ips(ips, medicamento_id)
        except Exception:
            logger.exception("La IPS %s no respondió a la consulta de disponibilidad", ips.codigo)
            no_disponibles.append(IPSNoDisponible(ips_id=ips.id, ips_nombre=ips.nombre_ficticio))
            continue
        for inventario, punto in filas:
            todas.append((ips, inventario, punto))

    def distancia(fila) -> float:
        return calculador.distancia_km(lat_usuario, lng_usuario, float(fila[2].lat), float(fila[2].lng))

    con_stock = [fila for fila in todas if fila[1].cantidad > 0]
    if con_stock:
        ciudad_usuario_normalizada = _normalizar_ciudad(ciudad_usuario)
        misma_ciudad = [fila for fila in con_stock if _normalizar_ciudad(fila[2].ciudad) == ciudad_usuario_normalizada]
        otra_ciudad = [fila for fila in con_stock if _normalizar_ciudad(fila[2].ciudad) != ciudad_usuario_normalizada]
        misma_ciudad.sort(key=distancia)
        resultados = [
            _a_resultado(ips, inv, punto, "punto_mas_cercano" if i == 0 else "otro_punto_ciudad", distancia((ips, inv, punto)))
            for i, (ips, inv, punto) in enumerate(misma_ciudad)
        ]
        resultados += [_a_resultado(ips, inv, punto, "otra_ciudad", distancia((ips, inv, punto))) for ips, inv, punto in otra_ciudad]
    else:
        todas.sort(key=lambda fila: (fila[1].fecha_reabastecimiento is None, fila[1].fecha_reabastecimiento))
        resultados = [_a_resultado(ips, inv, punto, "no_disponible", distancia((ips, inv, punto))) for ips, inv, punto in todas]

    aviso = None
    if no_disponibles:
        nombres = ", ".join(ips.ips_nombre for ips in no_disponibles)
        aviso = f"Algunas IPS están temporalmente fuera de servicio y no aparecen en los resultados: {nombres}."
    return RespuestaDisponibilidad(resultados=resultados, ips_no_disponibles=no_disponibles, aviso=aviso)


def _a_resultado(
    ips: InstitucionPrestadora, inventario: Inventario, punto: PuntoVenta, nivel: str, distancia_km: float
) -> ResultadoDisponibilidad:
    return ResultadoDisponibilidad(
        ips_id=ips.id,
        ips_nombre=ips.nombre_ficticio,
        punto_id=punto.id,
        punto_nombre=punto.nombre,
        ciudad=punto.ciudad,
        direccion=punto.direccion,
        lat=float(punto.lat),
        lng=float(punto.lng),
        distancia_km=round(distancia_km, 2),
        cantidad=inventario.cantidad,
        fecha_reabastecimiento=inventario.fecha_reabastecimiento,
        nivel=nivel,
    )
