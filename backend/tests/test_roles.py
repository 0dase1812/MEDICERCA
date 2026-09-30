from fastapi.testclient import TestClient

from app.models.usuario import RolUsuario

from tests.conftest import archivo_formula_prueba


def _medicamento_payload() -> dict[str, object]:
    return {
        "nombre_generico": "Ibuprofeno",
        "nombre_comercial": "Ibuprofeno Prueba",
        "dosis": "400 mg",
        "presentacion": "Tabletas x 10",
        "condicion_venta": "OTC",
        "control_especial": False,
        "registro_sanitario": "INVIMA-PRUEBA-001",
        "indicaciones_uso": "Tomar 1 tableta cada 8 horas.",
        "cantidad_por_entrega": "1 caja",
        "duracion_tratamiento_dias": 10,
    }


def _crear_medicamento(client: TestClient, token_factory) -> int:
    """Crea un medicamento vía la API usando un regente de una IPS cualquiera."""
    respuesta = client.post(
        "/api/v1/medicamentos",
        json=_medicamento_payload(),
        headers=token_factory(rol=RolUsuario.REGENTE, ips_id=1),
    )
    assert respuesta.status_code == 201
    return respuesta.json()["id"]


def test_paciente_no_puede_administrar_catalogo(client: TestClient, token_factory) -> None:
    response = client.post(
        "/api/v1/medicamentos",
        json=_medicamento_payload(),
        headers=token_factory(),
    )

    assert response.status_code == 403
    assert "regente" in response.json()["detail"].lower()


def test_regente_puede_administrar_catalogo(client: TestClient, token_factory) -> None:
    response = client.post(
        "/api/v1/medicamentos",
        json=_medicamento_payload(),
        headers=token_factory(rol=RolUsuario.REGENTE, ips_id=1),
    )

    assert response.status_code == 201
    assert response.json()["nombre_generico"] == "Ibuprofeno"


def test_solo_regente_de_la_misma_ips_puede_aprobar_orden(client: TestClient, token_factory) -> None:
    medicamento_id = _crear_medicamento(client, token_factory)
    paciente = token_factory(ips_id=1)
    orden = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente,
    )
    assert orden.status_code == 201
    orden_id = orden.json()["id"]

    paciente_intenta_aprobar = client.post(
        f"/api/v1/ordenes/1/{orden_id}/aprobar",
        headers=paciente,
    )
    assert paciente_intenta_aprobar.status_code == 403

    regente_de_otra_ips = token_factory(rol=RolUsuario.REGENTE, ips_id=2)
    otra_ips_intenta_aprobar = client.post(
        f"/api/v1/ordenes/1/{orden_id}/aprobar",
        headers=regente_de_otra_ips,
    )
    assert otra_ips_intenta_aprobar.status_code == 403

    regente_correcto = token_factory(nombre="Regente IPS 1", rol=RolUsuario.REGENTE, ips_id=1)
    aprobacion = client.post(
        f"/api/v1/ordenes/1/{orden_id}/aprobar",
        headers=regente_correcto,
    )
    assert aprobacion.status_code == 200
    assert aprobacion.json()["estado"] == "aprobada"
    assert aprobacion.json()["revisado_por"] == "Regente IPS 1"


def test_no_se_puede_cargar_orden_con_medicamento_inexistente(client: TestClient, token_factory) -> None:
    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": 999999},
        files=archivo_formula_prueba(),
        headers=token_factory(ips_id=1),
    )

    assert response.status_code == 404
    assert "medicamento" in response.json()["detail"].lower()


def test_paciente_no_puede_subir_orden_a_otra_ips(client: TestClient, token_factory) -> None:
    medicamento_id = _crear_medicamento(client, token_factory)
    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 2, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=token_factory(ips_id=1),
    )

    assert response.status_code == 403
    assert "ips vigente" in response.json()["detail"].lower()


def test_mis_ordenes_solo_devuelve_las_del_usuario_autenticado(client: TestClient, token_factory) -> None:
    medicamento_id = _crear_medicamento(client, token_factory)
    paciente = token_factory(cedula="1111111111", ips_id=1)
    otro_paciente = token_factory(cedula="2222222222", ips_id=1)

    client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente,
    )
    client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=otro_paciente,
    )

    mias = client.get("/api/v1/ordenes/mias", headers=paciente)
    assert mias.status_code == 200
    body = mias.json()
    assert len(body) == 1
    assert body[0]["usuario_cedula"] == "1111111111"


def test_ordenes_pendientes_solo_para_regente_y_filtra_por_estado(client: TestClient, token_factory) -> None:
    medicamento_id = _crear_medicamento(client, token_factory)
    paciente = token_factory(cedula="3333333333", ips_id=1)

    orden = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente,
    )
    orden_id = orden.json()["id"]

    paciente_intenta = client.get("/api/v1/ordenes/pendientes", headers=paciente)
    assert paciente_intenta.status_code == 403

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    pendientes = client.get("/api/v1/ordenes/pendientes", headers=regente)
    assert pendientes.status_code == 200
    assert any(o["id"] == orden_id for o in pendientes.json())

    client.post(f"/api/v1/ordenes/1/{orden_id}/aprobar", headers=regente)

    pendientes_despues = client.get("/api/v1/ordenes/pendientes", headers=regente)
    assert all(o["id"] != orden_id for o in pendientes_despues.json())


def test_obtener_orden_por_id_permite_dueno_y_regente_pero_no_a_otro_paciente(
    client: TestClient, token_factory
) -> None:
    medicamento_id = _crear_medicamento(client, token_factory)
    paciente = token_factory(cedula="4444444444", ips_id=1)
    orden = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente,
    )
    orden_id = orden.json()["id"]

    propio = client.get(f"/api/v1/ordenes/1/{orden_id}", headers=paciente)
    assert propio.status_code == 200

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    como_regente = client.get(f"/api/v1/ordenes/1/{orden_id}", headers=regente)
    assert como_regente.status_code == 200

    otro_paciente = token_factory(cedula="5555555555", ips_id=1)
    ajeno = client.get(f"/api/v1/ordenes/1/{orden_id}", headers=otro_paciente)
    assert ajeno.status_code == 403
