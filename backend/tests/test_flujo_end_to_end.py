"""Prueba de humo que encadena el flujo de negocio completo llamando a los
endpoints reales de principio a fin (registro -> verificacion -> login ->
cargar orden -> aprobar orden -> crear domicilio -> actualizar estado hasta
entrega). Las demas pruebas cubren cada endpoint de forma aislada; esta
detecta regresiones de integracion que solo aparecen al encadenarlos."""
from fastapi.testclient import TestClient

from app.models.usuario import RolUsuario
from app.models_ips import PuntoVenta

from tests.conftest import archivo_formula_prueba


def test_flujo_completo_registro_hasta_domicilio_entregado(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    # 1. Registro publico del paciente.
    datos_paciente = {
        "nombre": "Carlos Flujo",
        "cedula": "3030303030",
        "correo": "carlos.flujo@correo.com",
        "password": "ClaveSegura123",
        "ips_id": 1,
    }
    registro = client.post("/api/v1/auth/register", json=datos_paciente)
    assert registro.status_code == 201
    codigo = registro.json()["codigo_demo"]

    # 2. Verificacion de correo con el OTP simulado.
    verificacion = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos_paciente["correo"], "codigo": codigo},
    )
    assert verificacion.status_code == 200

    # 3. Login real (no via token_factory) para obtener el token del paciente.
    login = client.post(
        "/api/v1/auth/login",
        json={"correo": datos_paciente["correo"], "password": datos_paciente["password"]},
    )
    assert login.status_code == 200
    paciente_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 4. Un regente de la misma IPS da de alta el medicamento RX en el catalogo.
    regente_headers = token_factory(nombre="Regente Flujo", rol=RolUsuario.REGENTE, ips_id=1)
    medicamento = client.post(
        "/api/v1/medicamentos",
        json={
            "nombre_generico": "Losartan",
            "nombre_comercial": "Losartan Flujo",
            "dosis": "50 mg",
            "presentacion": "Tabletas x 30",
            "condicion_venta": "RX",
            "control_especial": False,
            "registro_sanitario": "INVIMA-FLUJO-001",
            "indicaciones_uso": "Tomar 1 tableta cada 24 horas.",
            "cantidad_por_entrega": "2 cajas",
            "duracion_tratamiento_dias": 60,
        },
        headers=regente_headers,
    )
    assert medicamento.status_code == 201
    medicamento_id = medicamento.json()["id"]

    # 5. El paciente carga la formula medica (un archivo real) que ampara ese medicamento.
    orden = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente_headers,
    )
    assert orden.status_code == 201
    assert orden.json()["estado"] == "pendiente"
    assert orden.json()["archivo_url"].startswith("data:image/png;base64,")
    assert orden.json()["aprobado_en"] is None
    orden_id = orden.json()["id"]

    # Punto de venta sembrado directamente (no existe endpoint publico para crearlo).
    with ips_db(1) as db:
        punto = PuntoVenta(
            nombre="Sede Flujo",
            ciudad="Bogotá",
            direccion="Calle 100 # 20-30",
            lat=4.6800,
            lng=-74.0500,
        )
        db.add(punto)
        db.commit()
        db.refresh(punto)
        punto_id = punto.id

    # Con la orden todavia pendiente, el RX no puede pedirse a domicilio.
    rechazado_por_pendiente = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente_headers,
    )
    assert rechazado_por_pendiente.status_code == 422

    # 6. El regente aprueba la orden.
    aprobacion = client.post(f"/api/v1/ordenes/1/{orden_id}/aprobar", headers=regente_headers)
    assert aprobacion.status_code == 200
    assert aprobacion.json()["estado"] == "aprobada"

    # 7. Con la orden aprobada, el paciente si puede crear el domicilio.
    domicilio = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente_headers,
    )
    assert domicilio.status_code == 201
    assert domicilio.json()["estado"] == "confirmado"
    domicilio_id = domicilio.json()["id"]

    # 8. El regente actualiza el estado logistico hasta la entrega.
    en_camino = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado",
        json={"estado": "en_camino", "lat_actual": 4.679, "lng_actual": -74.051},
        headers=regente_headers,
    )
    assert en_camino.status_code == 200
    assert en_camino.json()["estado"] == "en_camino"

    entregado = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado",
        json={"estado": "entregado"},
        headers=regente_headers,
    )
    assert entregado.status_code == 200
    assert entregado.json()["estado"] == "entregado"

    # 9. El paciente puede consultar el estado final de su domicilio.
    seguimiento = client.get(f"/api/v1/domicilios/1/{domicilio_id}", headers=paciente_headers)
    assert seguimiento.status_code == 200
    assert seguimiento.json()["estado"] == "entregado"

    # 10. El historial completo del pedido queda registrado en orden cronologico:
    # confirmado (al crear) -> en_camino -> entregado. Cada cambio de estado
    # queda como fila propia, ninguna se sobrescribe.
    historial = client.get(f"/api/v1/domicilios/1/{domicilio_id}/historial", headers=paciente_headers)
    assert historial.status_code == 200
    estados = [fila["estado"] for fila in historial.json()]
    assert estados == ["confirmado", "en_camino", "entregado"]
    # El punto intermedio quedo con las coordenadas que mando el regente en ese momento.
    assert historial.json()[1]["lat_actual"] == 4.679
