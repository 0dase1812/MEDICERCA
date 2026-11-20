"""Evidencia automatizada de los 6 escenarios de calidad de MediCerca.

Cada test lleva el prefijo del escenario que demuestra:

  test_seg_*    Seguridad       - protección contra acceso no autorizado
  test_mod_*    Modificabilidad - incorporar una IPS nueva
  test_disp_*   Disponibilidad  - falla de una IPS
  test_usab1_*  Usabilidad 1    - cancelar un domicilio pedido por error
  test_usab2_*  Usabilidad 2    - encontrar el punto de venta más cercano
  test_usab3_*  Usabilidad 3    - retroalimentación de cada acción

Correr solo esta evidencia:  pytest tests/test_escenarios_calidad.py -v
La guía para exponerlos está en docs/ESCENARIOS_CALIDAD.md.
"""
import math
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.models.medicamento import CondicionVenta, Medicamento
from app.models.usuario import RolUsuario, Usuario
from app.models_ips import EstadoOrden, Inventario, OrdenMedica, PuntoVenta

from tests.conftest import archivo_formula_prueba


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _medicamento(db_session, sufijo: str) -> int:
    medicamento = Medicamento(
        nombre_generico=f"Generico {sufijo}",
        nombre_comercial=f"Comercial {sufijo}",
        dosis="500 mg",
        presentacion="Tabletas x 10",
        condicion_venta=CondicionVenta.OTC,
        control_especial=False,
        registro_sanitario=f"INVIMA-QA-{sufijo}",
        indicaciones_uso="Tomar segun indicacion medica.",
        cantidad_por_entrega="1 caja",
        duracion_tratamiento_dias=30,
    )
    db_session.add(medicamento)
    db_session.commit()
    db_session.refresh(medicamento)
    return medicamento.id


def _domicilio_confirmado(client, db_session, ips_db, token_factory, *, cedula: str, sufijo: str):
    """Deja listo un domicilio CONFIRMADO del paciente `cedula` en la IPS 1."""
    medicamento_id = _medicamento(db_session, sufijo)
    with ips_db(1) as db:
        orden = OrdenMedica(
            usuario_cedula=cedula,
            archivo_url="data:image/png;base64,AAAA",
            medicamento_id=medicamento_id,
            estado=EstadoOrden.APROBADA,
        )
        punto = PuntoVenta(nombre="Sede QA", ciudad="Bogotá", direccion="Calle 1 # 2-3", lat=4.65, lng=-74.06)
        db.add_all([orden, punto])
        db.commit()
        db.refresh(orden)
        db.refresh(punto)
        orden_id, punto_id = orden.id, punto.id
    headers = token_factory(cedula=cedula, ips_id=1)
    respuesta = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=headers,
    )
    assert respuesta.status_code == 201, respuesta.text
    return {"headers": headers, "domicilio_id": respuesta.json()["id"], "orden_id": orden_id,
            "punto_id": punto_id, "medicamento_id": medicamento_id}


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Implementación independiente (para no validar el código con el mismo código)."""
    r = 6371.0
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


PUNTOS_BOGOTA = {
    1: [("Chapinero", 4.6486, -74.0625), ("Kennedy", 4.6280, -74.1567)],
    2: [("Suba", 4.7480, -74.0930), ("Teusaquillo", 4.6320, -74.0910)],
    3: [("Fontibon", 4.6675, -74.1469), ("Ciudad Bolivar", 4.5709, -74.1646)],
}


def _sembrar_puntos(db_session, ips_db, sufijo: str) -> int:
    medicamento_id = _medicamento(db_session, sufijo)
    for ips_id, puntos in PUNTOS_BOGOTA.items():
        with ips_db(ips_id) as db:
            for nombre, lat, lng in puntos:
                punto = PuntoVenta(nombre=nombre, ciudad="Bogotá", direccion=f"Direccion {nombre}", lat=lat, lng=lng)
                db.add(punto)
                db.flush()
                db.add(Inventario(punto_id=punto.id, medicamento_id=medicamento_id, cantidad=10))
            db.commit()
    return medicamento_id


# ===========================================================================
# SEGURIDAD - protección contra acceso no autorizado
# ===========================================================================

def test_seg_bloqueo_tras_cinco_fallos_rechaza_el_100_por_ciento_de_los_intentos(client, usuario_factory) -> None:
    usuario = usuario_factory()
    for _ in range(5):
        assert client.post(
            "/api/v1/auth/login", json={"correo": usuario["correo"], "password": "ClaveIncorrecta1"}
        ).status_code == 401

    # Desde el sexto intento TODO se rechaza, incluso la contraseña correcta.
    intentos = [usuario["password"], "ClaveIncorrecta1", usuario["password"], "OtraMala123"]
    codigos = [
        client.post("/api/v1/auth/login", json={"correo": usuario["correo"], "password": clave}).status_code
        for clave in intentos
    ]
    assert codigos == [429, 429, 429, 429]


def test_seg_el_bloqueo_vence_y_el_contador_empieza_de_cero(client, usuario_factory, db_session) -> None:
    """Regresión: antes, al vencer los 15 minutos el contador seguía en 5 y UN solo error
    más volvía a bloquear la cuenta (no eran '5 intentos consecutivos')."""
    usuario = usuario_factory()
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"correo": usuario["correo"], "password": "ClaveIncorrecta1"})

    registro = db_session.query(Usuario).filter(Usuario.correo == usuario["correo"]).one()
    assert registro.bloqueado_hasta is not None
    registro.bloqueado_hasta = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    un_fallo = client.post("/api/v1/auth/login", json={"correo": usuario["correo"], "password": "ClaveIncorrecta1"})
    assert un_fallo.status_code == 401  # NO 429: el contador se reinició

    db_session.expire_all()
    assert db_session.query(Usuario).filter(Usuario.correo == usuario["correo"]).one().intentos_fallidos == 1

    correcto = client.post("/api/v1/auth/login", json={"correo": usuario["correo"], "password": usuario["password"]})
    assert correcto.status_code == 200


def test_seg_un_otp_ya_usado_no_se_puede_reutilizar(client) -> None:
    datos = {"nombre": "Ana OTP", "cedula": "1717171717", "correo": "ana.otp@correo.com",
             "password": "ClaveSegura123", "ips_id": 1}
    codigo = client.post("/api/v1/auth/register", json=datos).json()["codigo_demo"]

    primera = client.post("/api/v1/auth/verificar-registro", json={"correo": datos["correo"], "codigo": codigo})
    assert primera.status_code == 200

    segunda = client.post("/api/v1/auth/verificar-registro", json={"correo": datos["correo"], "codigo": codigo})
    assert segunda.status_code == 400


def test_seg_token_revocado_es_rechazado_en_todos_los_endpoints_protegidos(client, token_factory) -> None:
    headers = token_factory()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    protegidos = ["/api/v1/auth/me", "/api/v1/ordenes/mias", "/api/v1/domicilios/mias", "/api/v1/historia-clinica/mia"]
    codigos = [client.get(ruta, headers=headers).status_code for ruta in protegidos]
    assert codigos == [401, 401, 401, 401]


def test_seg_acceso_cruzado_entre_pacientes_se_niega_al_100_por_ciento(
    client, db_session, ips_db, token_factory
) -> None:
    ajeno = _domicilio_confirmado(client, db_session, ips_db, token_factory, cedula="1818181818", sufijo="SEGX")
    intruso = token_factory(cedula="1919191919", ips_id=1)
    d, o = ajeno["domicilio_id"], ajeno["orden_id"]

    respuestas = [
        client.get(f"/api/v1/domicilios/1/{d}", headers=intruso),
        client.get(f"/api/v1/domicilios/1/{d}/historial", headers=intruso),
        client.post(f"/api/v1/domicilios/1/{d}/cancelar", headers=intruso),
        client.get(f"/api/v1/ordenes/1/{o}", headers=intruso),
        client.get(f"/api/v1/ordenes/1/{o}/historial", headers=intruso),
        client.post(f"/api/v1/ordenes/1/{o}/aprobar", headers=intruso),
    ]
    assert [r.status_code for r in respuestas] == [403] * 6


# ===========================================================================
# MODIFICABILIDAD - incorporar una IPS nueva
# ===========================================================================

def test_mod_registrar_ips_exige_clave_de_administracion_y_configuracion_previa(client, monkeypatch) -> None:
    cuerpo = {"codigo": "IPS-NUEVA", "nombre_ficticio": "IPS Nueva", "clave_conexion": "demo_ips_9"}

    sin_clave = client.post("/api/v1/admin/ips", json=cuerpo)
    assert sin_clave.status_code == 422
    clave_mala = client.post("/api/v1/admin/ips", json=cuerpo, headers={"X-Admin-Key": "no-es-la-clave"})
    assert clave_mala.status_code == 401

    # Con la clave correcta, pero SIN la variable de entorno con la URL: se rechaza con un mensaje claro.
    monkeypatch.delenv("DATABASE_URL_IPS_9", raising=False)
    sin_configurar = client.post("/api/v1/admin/ips", json=cuerpo, headers={"X-Admin-Key": settings.admin_key})
    assert sin_configurar.status_code == 422
    assert "DATABASE_URL_IPS_" in sin_configurar.json()["detail"]


def test_mod_una_ips_nueva_funciona_solo_con_configuracion_sin_tocar_codigo(
    client, db_session, ips_db, token_factory, monkeypatch, tmp_path
) -> None:
    from app.ips_db import IPSBase, get_engine_para_pruebas, limpiar_conexiones_ips_para_pruebas

    # PASO 1 (configuración): la URL real de la IPS 4 se declara como variable de entorno.
    url = f"sqlite:///{(tmp_path / 'ips_4.sqlite3').as_posix()}?check_same_thread=False"
    monkeypatch.setenv("DATABASE_URL_IPS_4", url)
    try:
        IPSBase.metadata.create_all(bind=get_engine_para_pruebas("demo_ips_4"))

        # PASO 2 (registro dinámico): se da de alta en la tabla central `ips`. Cero cambios de código.
        alta = client.post(
            "/api/v1/admin/ips",
            headers={"X-Admin-Key": settings.admin_key},
            json={"codigo": "IPS-NORTE", "nombre_ficticio": "IPS Norte Integrada", "clave_conexion": "demo_ips_4"},
        )
        assert alta.status_code == 201, alta.text
        ips_id = alta.json()["id"]
        assert alta.json()["tipo_integracion"] == "base_datos_directa"

        # Aparece en el listado público de IPS.
        assert any(i["id"] == ips_id for i in client.get("/api/v1/ips").json()["items"])

        # El health check la incluye sin tocar nada.
        salud = client.get("/api/v1/health").json()
        assert salud["bases_de_datos"]["demo_ips_4"] is True

        # Disponibilidad: el módulo existente ya consulta la IPS nueva.
        medicamento_id = _medicamento(db_session, "MOD4")
        with ips_db(ips_id) as db:
            punto = PuntoVenta(nombre="Sede IPS Nueva", ciudad="Bogotá", direccion="Av 1 # 1-1", lat=4.70, lng=-74.05)
            db.add(punto)
            db.flush()
            db.add(Inventario(punto_id=punto.id, medicamento_id=medicamento_id, cantidad=7))
            db.commit()
        disponibilidad = client.post(
            "/api/v1/disponibilidad",
            json={"medicamento_id": medicamento_id, "lat_usuario": 4.70, "lng_usuario": -74.05, "ciudad_usuario": "Bogotá"},
        ).json()
        assert [r["ips_id"] for r in disponibilidad["resultados"]] == [ips_id]

        # Órdenes: un paciente afiliado a la IPS nueva opera con los módulos de siempre.
        paciente = token_factory(ips_id=ips_id)
        orden = client.post(
            "/api/v1/ordenes",
            data={"ips_id": ips_id, "medicamento_id": medicamento_id},
            files=archivo_formula_prueba(),
            headers=paciente,
        )
        assert orden.status_code == 201
    finally:
        limpiar_conexiones_ips_para_pruebas()


def test_mod_no_se_puede_registrar_dos_veces_la_misma_ips(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL_IPS_5", f"sqlite:///{(tmp_path / 'ips_5.sqlite3').as_posix()}?check_same_thread=False")
    cuerpo = {"codigo": "IPS-DUP", "nombre_ficticio": "IPS Dup", "clave_conexion": "demo_ips_5"}
    headers = {"X-Admin-Key": settings.admin_key}
    from app.ips_db import limpiar_conexiones_ips_para_pruebas
    try:
        assert client.post("/api/v1/admin/ips", json=cuerpo, headers=headers).status_code == 201
        assert client.post("/api/v1/admin/ips", json=cuerpo, headers=headers).status_code == 400
    finally:
        limpiar_conexiones_ips_para_pruebas()


# ===========================================================================
# DISPONIBILIDAD - falla de una IPS
# ===========================================================================

class _EngineCaido:
    def connect(self):
        raise RuntimeError("IPS caída (simulado)")


def test_disp_health_responde_503_e_identifica_la_ips_caida(client, monkeypatch) -> None:
    import app.main as principal

    original = principal.obtener_engine_ips
    monkeypatch.setattr(
        principal, "obtener_engine_ips", lambda clave: _EngineCaido() if clave == "demo_ips_2" else original(clave)
    )

    inicio = time.perf_counter()
    respuesta = client.get("/api/v1/health")
    duracion = time.perf_counter() - inicio

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degraded"
    assert cuerpo["bases_de_datos"] == {"central": True, "demo_ips_1": True, "demo_ips_2": False, "demo_ips_3": True}
    assert duracion < 30  # la medida del escenario es detectar la falla en menos de 30 s


def test_disp_la_consulta_devuelve_resultados_parciales_con_aviso(client, db_session, ips_db, monkeypatch) -> None:
    import app.core.availability_engine as motor

    medicamento_id = _sembrar_puntos(db_session, ips_db, "DISP1")
    original = motor._consultar_una_ips

    def falla_la_ips_2(ips, med_id):
        if ips.id == 2:
            raise ConnectionError("IPS 2 no responde (simulado)")
        return original(ips, med_id)

    monkeypatch.setattr(motor, "_consultar_una_ips", falla_la_ips_2)

    inicio = time.perf_counter()
    respuesta = client.post(
        "/api/v1/disponibilidad",
        json={"medicamento_id": medicamento_id, "lat_usuario": 4.65, "lng_usuario": -74.06, "ciudad_usuario": "Bogotá"},
    )
    duracion = time.perf_counter() - inicio

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert {r["ips_id"] for r in cuerpo["resultados"]} == {1, 3}
    assert cuerpo["ips_no_disponibles"] == [{"ips_id": 2, "ips_nombre": "IPS Somos Salud"}]
    assert "fuera de servicio" in cuerpo["aviso"]
    assert duracion < 5  # ninguna respuesta tarda más de 5 s por culpa de la IPS caída


def test_disp_sin_fallas_no_hay_aviso(client, db_session, ips_db) -> None:
    medicamento_id = _sembrar_puntos(db_session, ips_db, "DISP2")
    cuerpo = client.post(
        "/api/v1/disponibilidad",
        json={"medicamento_id": medicamento_id, "lat_usuario": 4.65, "lng_usuario": -74.06, "ciudad_usuario": "Bogotá"},
    ).json()
    assert cuerpo["ips_no_disponibles"] == []
    assert cuerpo["aviso"] is None
    assert {r["ips_id"] for r in cuerpo["resultados"]} == {1, 2, 3}


def test_disp_los_pacientes_de_otra_ips_siguen_operando_durante_la_falla(
    client, db_session, token_factory, monkeypatch
) -> None:
    """Aislamiento de fallas: con la IPS 2 caída, un paciente de la IPS 1 sigue cargando
    órdenes y consultando su historial como siempre."""
    import app.main as principal

    original = principal.obtener_engine_ips
    monkeypatch.setattr(
        principal, "obtener_engine_ips", lambda clave: _EngineCaido() if clave == "demo_ips_2" else original(clave)
    )
    medicamento_id = _medicamento(db_session, "DISP3")
    paciente = token_factory(ips_id=1)

    exitosas = 0
    intentos = 20
    for _ in range(intentos):
        orden = client.post(
            "/api/v1/ordenes",
            data={"ips_id": 1, "medicamento_id": medicamento_id},
            files=archivo_formula_prueba(),
            headers=paciente,
        )
        exitosas += orden.status_code == 201
    assert exitosas / intentos >= 0.95
    assert client.get("/api/v1/ordenes/mias", headers=paciente).status_code == 200


# ===========================================================================
# USABILIDAD 1 - cancelar un domicilio pedido por error
# (la confirmación "¿Seguro?" y el botón visible están en el frontend; aquí se
#  prueba la regla que protege al paciente)
# ===========================================================================

def test_usab1_el_paciente_cancela_en_un_paso_y_la_orden_queda_libre(client, db_session, ips_db, token_factory) -> None:
    d = _domicilio_confirmado(client, db_session, ips_db, token_factory, cedula="2121212121", sufijo="U1A")

    cancelado = client.post(f"/api/v1/domicilios/1/{d['domicilio_id']}/cancelar", headers=d["headers"])
    assert cancelado.status_code == 200
    assert cancelado.json()["estado"] == "cancelado"

    # La cancelación queda en la línea de tiempo.
    historial = client.get(f"/api/v1/domicilios/1/{d['domicilio_id']}/historial", headers=d["headers"]).json()
    assert [paso["estado"] for paso in historial] == ["confirmado", "cancelado"]

    # La orden queda libre: puede volver a pedirse sin cargar otra fórmula.
    nuevo = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": d["orden_id"], "punto_origen_id": d["punto_id"],
              "medicamento_id": d["medicamento_id"]},
        headers=d["headers"],
    )
    assert nuevo.status_code == 201


def test_usab1_un_domicilio_en_camino_ya_no_se_puede_cancelar_y_el_mensaje_es_claro(
    client, db_session, ips_db, token_factory
) -> None:
    d = _domicilio_confirmado(client, db_session, ips_db, token_factory, cedula="2222222221", sufijo="U1B")
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    client.patch(f"/api/v1/domicilios/1/{d['domicilio_id']}/estado", json={"estado": "en_camino"}, headers=regente)

    respuesta = client.post(f"/api/v1/domicilios/1/{d['domicilio_id']}/cancelar", headers=d["headers"])
    assert respuesta.status_code == 422
    assert "ya no se puede cancelar" in respuesta.json()["detail"]


# ===========================================================================
# USABILIDAD 2 - encontrar el punto de venta más cercano
# ===========================================================================

def test_usab2_el_primer_resultado_es_el_punto_mas_cercano_en_el_100_por_ciento_de_los_casos(
    client, db_session, ips_db
) -> None:
    medicamento_id = _sembrar_puntos(db_session, ips_db, "U2A")
    todos = [(n, lat, lng) for puntos in PUNTOS_BOGOTA.values() for n, lat, lng in puntos]

    ubicaciones = [(4.6490, -74.0602), (4.60, -74.15), (4.75, -74.09), (4.67, -74.14), (4.57, -74.16)]
    for lat_u, lng_u in ubicaciones:
        respuesta = client.post(
            "/api/v1/disponibilidad",
            json={"medicamento_id": medicamento_id, "lat_usuario": lat_u, "lng_usuario": lng_u, "ciudad_usuario": "Bogotá"},
        ).json()["resultados"]
        esperado = min(todos, key=lambda p: _haversine_km(lat_u, lng_u, p[1], p[2]))[0]
        assert respuesta[0]["punto_nombre"] == esperado
        assert respuesta[0]["nivel"] == "punto_mas_cercano"
        # y el resto viene ordenado por distancia creciente
        distancias = [r["distancia_km"] for r in respuesta]
        assert distancias == sorted(distancias)


def test_usab2_cada_resultado_trae_direccion_distancia_y_coordenadas_para_el_mapa(client, db_session, ips_db) -> None:
    medicamento_id = _sembrar_puntos(db_session, ips_db, "U2B")
    primero = client.post(
        "/api/v1/disponibilidad",
        json={"medicamento_id": medicamento_id, "lat_usuario": 4.6490, "lng_usuario": -74.0602, "ciudad_usuario": "Bogotá"},
    ).json()["resultados"][0]

    assert primero["direccion"] == "Direccion Chapinero"
    assert primero["lat"] == 4.6486 and primero["lng"] == -74.0625
    esperado = round(_haversine_km(4.6490, -74.0602, 4.6486, -74.0625), 2)
    assert primero["distancia_km"] == esperado


def test_usab2_la_consulta_responde_en_menos_de_3_segundos(client, db_session, ips_db) -> None:
    medicamento_id = _sembrar_puntos(db_session, ips_db, "U2C")
    inicio = time.perf_counter()
    respuesta = client.post(
        "/api/v1/disponibilidad",
        json={"medicamento_id": medicamento_id, "lat_usuario": 4.65, "lng_usuario": -74.06, "ciudad_usuario": "Bogotá"},
    )
    assert respuesta.status_code == 200
    assert time.perf_counter() - inicio < 3


# ===========================================================================
# USABILIDAD 3 - retroalimentación de cada acción
# (el aviso verde/rojo en pantalla es del frontend; aquí se prueba la
#  confirmación por correo y el tiempo de respuesta de la acción)
# ===========================================================================

def test_usab3_crear_un_domicilio_envia_correo_de_confirmacion_en_menos_de_1_segundo(
    client, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _medicamento(db_session, "U3A")
    with ips_db(1) as db:
        orden = OrdenMedica(usuario_cedula="2323232323", archivo_url="data:image/png;base64,AAAA",
                            medicamento_id=medicamento_id, estado=EstadoOrden.APROBADA)
        punto = PuntoVenta(nombre="Sede U3", ciudad="Bogotá", direccion="Calle 9 # 9-9", lat=4.65, lng=-74.06)
        db.add_all([orden, punto])
        db.commit()
        db.refresh(orden)
        db.refresh(punto)
        orden_id, punto_id = orden.id, punto.id
    headers = token_factory(cedula="2323232323", ips_id=1, correo="paciente.u3@correo.com", nombre="Paciente U3")

    with patch("app.api.v1.routes.domicilios.enviar_correo") as correo:
        inicio = time.perf_counter()
        respuesta = client.post(
            "/api/v1/domicilios",
            json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
            headers=headers,
        )
        duracion = time.perf_counter() - inicio

    assert respuesta.status_code == 201
    assert duracion < 1.0
    correo.assert_called_once()
    destinatario, asunto, cuerpo = correo.call_args.args
    assert destinatario == "paciente.u3@correo.com"
    assert f"#{respuesta.json()['id']}" in cuerpo and "fue confirmado" in cuerpo
    assert "Fecha y hora" in cuerpo


def test_usab3_cancelar_un_domicilio_tambien_envia_correo(client, db_session, ips_db, token_factory) -> None:
    d = _domicilio_confirmado(client, db_session, ips_db, token_factory, cedula="2424242424", sufijo="U3B")
    with patch("app.api.v1.routes.domicilios.enviar_correo") as correo:
        respuesta = client.post(f"/api/v1/domicilios/1/{d['domicilio_id']}/cancelar", headers=d["headers"])
    assert respuesta.status_code == 200
    correo.assert_called_once()
    assert "fue cancelado" in correo.call_args.args[2]


def test_usab3_el_error_de_una_accion_trae_un_mensaje_entendible(client, token_factory) -> None:
    """Un error NO debe ser un código técnico: el frontend lo muestra en rojo tal cual."""
    respuesta = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": 1},
        files={"archivo": ("formula.txt", b"hola", "text/plain")},
        headers=token_factory(ips_id=1),
    )
    assert respuesta.status_code in (404, 422)
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle, str) and len(detalle) > 10
