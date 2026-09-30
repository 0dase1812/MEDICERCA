"""Casos borde de ordenes/domicilios no cubiertos por test_reglas_legales.py
ni test_roles.py: autenticacion ausente, afiliacion invalida, referencias
inexistentes (orden/punto de venta), acceso cruzado entre pacientes, y el
limite exacto entre medicamentos OTC y RX en la regla de "orden aprobada"."""
from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models.usuario import RolUsuario
from app.models_ips import EstadoOrden, OrdenMedica, PuntoVenta

from tests.conftest import archivo_formula_prueba


def _crear_medicamento(db_session, *, rx: bool, sufijo: str) -> int:
    medicamento = Medicamento(
        nombre_generico=f"Medicamento {sufijo}",
        nombre_comercial=f"Comercial {sufijo}",
        dosis="500 mg",
        presentacion="Tabletas x 10",
        condicion_venta=CondicionVenta.RX if rx else CondicionVenta.OTC,
        control_especial=False,
        registro_sanitario=f"INVIMA-{sufijo}",
        indicaciones_uso="Tomar segun indicacion medica.",
        cantidad_por_entrega="1 caja",
        duracion_tratamiento_dias=30,
    )
    db_session.add(medicamento)
    db_session.commit()
    db_session.refresh(medicamento)
    return medicamento.id


def _crear_orden(ips_db, *, estado: EstadoOrden, medicamento_id: int, cedula: str) -> int:
    with ips_db(1) as db:
        orden = OrdenMedica(
            usuario_cedula=cedula,
            archivo_url="https://ejemplo.test/formula.pdf",
            medicamento_id=medicamento_id,
            estado=estado,
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)
        return orden.id


def _crear_punto_venta(ips_db, ips_id: int = 1) -> int:
    with ips_db(ips_id) as db:
        punto = PuntoVenta(
            nombre="Sede de prueba",
            ciudad="Bogotá",
            direccion="Calle 1 # 2-3",
            lat=4.6500,
            lng=-74.0600,
        )
        db.add(punto)
        db.commit()
        db.refresh(punto)
        return punto.id


# ---------------------------------------------------------------------------
# Sin token
# ---------------------------------------------------------------------------

def test_crear_domicilio_sin_token_devuelve_401(client: TestClient, db_session, ips_db) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="AUTH1")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
    )

    assert response.status_code == 401


def test_cargar_orden_sin_token_devuelve_401(client: TestClient, db_session) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="AUTH2")

    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Afiliacion / IPS invalida
# ---------------------------------------------------------------------------

def test_usuario_sin_afiliacion_vigente_no_puede_cargar_orden(
    client: TestClient, db_session, token_factory
) -> None:
    """Un usuario que nunca se afilio a una IPS (ips_id=None en el factory) no
    tiene "IPS vigente": debe rechazarse antes de siquiera comparar contra el
    ips_id del payload."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="NOAFIL1")

    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=token_factory(ips_id=None),
    )

    assert response.status_code == 403
    assert "afiliacion" in response.json()["detail"].lower()


def test_usuario_sin_afiliacion_vigente_no_puede_crear_domicilio(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="NOAFIL2")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="9999999999")
    punto_id = _crear_punto_venta(ips_db)

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=token_factory(cedula="9999999999", ips_id=None),
    )

    assert response.status_code == 403
    assert "afiliacion" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Referencias inexistentes
# ---------------------------------------------------------------------------

def test_domicilio_con_orden_inexistente_devuelve_404(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="ORDNOEX")
    punto_id = _crear_punto_venta(ips_db)

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": 999999, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=token_factory(ips_id=1),
    )

    assert response.status_code == 404
    assert "orden" in response.json()["detail"].lower()


def test_domicilio_con_punto_de_venta_inexistente_devuelve_404(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="PUNTONOEX")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": 999999, "medicamento_id": medicamento_id},
        headers=token_factory(cedula="1010101010", ips_id=1),
    )

    assert response.status_code == 404
    assert "punto" in response.json()["detail"].lower()


def test_domicilio_con_orden_de_otro_paciente_no_autoriza(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="OTROPAC")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="5555555555")
    punto_id = _crear_punto_venta(ips_db)

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        # cedula del token es distinta a la duena de la orden (5555555555)
        headers=token_factory(cedula="1010101010", ips_id=1),
    )

    assert response.status_code == 403
    assert "otro paciente" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Limite OTC / RX (caso borde del fix de medicamento_id ya aplicado)
# ---------------------------------------------------------------------------

def test_medicamento_otc_no_requiere_orden_aprobada_para_domicilio(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """La exigencia de "orden aprobada" solo aplica a medicamentos RX
    (ver core.legal_rules.requiere_formula). Un OTC con una orden todavia
    PENDIENTE debe poder generar domicilio igual, para confirmar que la regla
    RX no se aplico de mas al corregir el gap de medicamento_id."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="OTCBORDE")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.PENDIENTE, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=token_factory(cedula="1010101010", ips_id=1),
    )

    assert response.status_code == 201
    assert response.json()["estado"] == "confirmado"


def test_no_se_puede_pedir_dos_domicilios_con_la_misma_orden(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """Una orden aprobada ampara UNA sola entrega: pedir un segundo domicilio
    reutilizando la misma orden debe rechazarse, no crear otro pedido."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="DOSDOMI")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="1010101010", ips_id=1)

    primero = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    assert primero.status_code == 201

    segundo = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    assert segundo.status_code == 422
    assert "ya tiene un domicilio" in segundo.json()["detail"].lower()


def test_paciente_puede_cancelar_domicilio_y_volver_a_pedirlo(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """El paciente dueño puede cancelar mientras el domicilio sigue
    confirmado, y una vez cancelado la orden queda libre para pedirlo de
    nuevo (no se queda bloqueada para siempre)."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="CANCELA")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="1010101010", ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    domicilio_id = creado.json()["id"]

    cancelado = client.post(f"/api/v1/domicilios/1/{domicilio_id}/cancelar", headers=paciente)
    assert cancelado.status_code == 200
    assert cancelado.json()["estado"] == "cancelado"

    otro_paciente = token_factory(cedula="3030303030", ips_id=1)
    ajeno = client.post(f"/api/v1/domicilios/1/{domicilio_id}/cancelar", headers=otro_paciente)
    assert ajeno.status_code == 403

    nuevo = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    assert nuevo.status_code == 201
    assert nuevo.json()["id"] != domicilio_id


def test_no_se_puede_cancelar_un_domicilio_ya_en_camino(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="NOCANCEL")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="1010101010", ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    domicilio_id = creado.json()["id"]

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    client.patch(f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "en_camino"}, headers=regente)

    respuesta = client.post(f"/api/v1/domicilios/1/{domicilio_id}/cancelar", headers=paciente)
    assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# Lectura y actualizacion de estado (sin tests previos)
# ---------------------------------------------------------------------------

def test_obtener_domicilio_niega_acceso_a_paciente_distinto(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="GETACC")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)
    dueno = token_factory(cedula="1010101010", ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=dueno,
    )
    assert creado.status_code == 201
    domicilio_id = creado.json()["id"]

    propio = client.get(f"/api/v1/domicilios/1/{domicilio_id}", headers=dueno)
    assert propio.status_code == 200

    otro_paciente = token_factory(cedula="2020202020", ips_id=1)
    ajeno = client.get(f"/api/v1/domicilios/1/{domicilio_id}", headers=otro_paciente)
    assert ajeno.status_code == 403


def test_actualizar_estado_domicilio_requiere_rol_regente(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="PATCHROL")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="1010101010")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="1010101010", ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    domicilio_id = creado.json()["id"]

    paciente_intenta = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado",
        json={"estado": "en_camino"},
        headers=paciente,
    )
    assert paciente_intenta.status_code == 403

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    actualizado = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado",
        json={"estado": "en_camino", "lat_actual": 4.65, "lng_actual": -74.06},
        headers=regente,
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["estado"] == "en_camino"
    assert actualizado.json()["lat_actual"] == 4.65


# ---------------------------------------------------------------------------
# Historial de estados: control de acceso
# ---------------------------------------------------------------------------

def test_paciente_no_puede_ver_historial_de_domicilio_ajeno(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """Mismo control de acceso que GET /{ips_id}/{domicilio_id}: un paciente
    solo puede ver el historial de SUS PROPIOS domicilios, no los de otro
    paciente de la misma IPS."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="HIST1")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="2020202020")
    punto_id = _crear_punto_venta(ips_db)
    dueño = token_factory(cedula="2020202020", ips_id=1)
    otro_paciente = token_factory(cedula="3030303030", ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=dueño,
    )
    domicilio_id = creado.json()["id"]

    intento_ajeno = client.get(f"/api/v1/domicilios/1/{domicilio_id}/historial", headers=otro_paciente)
    assert intento_ajeno.status_code == 403

    propio = client.get(f"/api/v1/domicilios/1/{domicilio_id}/historial", headers=dueño)
    assert propio.status_code == 200
    assert len(propio.json()) == 1
    assert propio.json()[0]["estado"] == "confirmado"


def test_mis_domicilios_solo_devuelve_los_del_usuario_autenticado(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="MISDOM")
    orden_propia = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="6060606060")
    orden_ajena = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="7070707070")
    punto_id = _crear_punto_venta(ips_db)
    dueno = token_factory(cedula="6060606060", ips_id=1)
    otro = token_factory(cedula="7070707070", ips_id=1)

    client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_propia, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=dueno,
    )
    client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_ajena, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=otro,
    )

    mios = client.get("/api/v1/domicilios/mias", headers=dueno)
    assert mios.status_code == 200
    assert len(mios.json()) == 1
    assert mios.json()[0]["orden_id"] == orden_propia


def test_domicilios_activos_solo_para_regente_y_excluye_entregados(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="DOMACT")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="8080808080")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="8080808080", ips_id=1)

    paciente_intenta = client.get("/api/v1/domicilios/activos", headers=paciente)
    assert paciente_intenta.status_code == 403

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    domicilio_id = creado.json()["id"]

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    activos = client.get("/api/v1/domicilios/activos", headers=regente)
    assert activos.status_code == 200
    assert any(d["id"] == domicilio_id for d in activos.json())

    client.patch(f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "entregado"}, headers=regente)

    activos_despues = client.get("/api/v1/domicilios/activos", headers=regente)
    assert all(d["id"] != domicilio_id for d in activos_despues.json())


def test_regente_no_puede_ver_historial_de_domicilio_de_otro_paciente(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """Mismo comportamiento que GET /{ips_id}/{domicilio_id} (su endpoint
    hermano): esta app restringe la lectura de un domicilio al paciente dueño,
    sin excepcion para el rol regente. El regente SI puede escribir (PATCH del
    estado, ver test_solo_regente_puede_actualizar_estado_de_domicilio), pero
    no leer el domicilio o historial de un paciente que no es el suyo."""
    medicamento_id = _crear_medicamento(db_session, rx=False, sufijo="HIST2")
    orden_id = _crear_orden(ips_db, estado=EstadoOrden.APROBADA, medicamento_id=medicamento_id, cedula="4040404040")
    punto_id = _crear_punto_venta(ips_db)
    paciente = token_factory(cedula="4040404040", ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    domicilio_id = creado.json()["id"]

    respuesta = client.get(f"/api/v1/domicilios/1/{domicilio_id}/historial", headers=regente)
    assert respuesta.status_code == 403
