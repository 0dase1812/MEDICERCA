"""Tests del endurecimiento de validaciones de entrada agregado en esta
sesion: rango de lat/lng (-90/90, -180/180) en disponibilidad y domicilios,
y tipo/tamaño del archivo (imagen o PDF) al cargar una orden."""
from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models_ips import EstadoOrden, OrdenMedica, PuntoVenta

from tests.conftest import archivo_formula_prueba


def _crear_medicamento(db_session, *, sufijo: str) -> int:
    medicamento = Medicamento(
        nombre_generico=f"Medicamento {sufijo}",
        nombre_comercial=f"Comercial {sufijo}",
        dosis="500 mg",
        presentacion="Tabletas x 10",
        condicion_venta=CondicionVenta.OTC,
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


# ---------------------------------------------------------------------------
# lat/lng fuera de rango
# ---------------------------------------------------------------------------

def test_disponibilidad_rechaza_latitud_fuera_de_rango(client: TestClient, db_session) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="LATRANGE")

    response = client.post(
        "/api/v1/disponibilidad",
        json={
            "medicamento_id": medicamento_id,
            "lat_usuario": 120.0,  # fuera de -90/90
            "lng_usuario": -74.06,
            "ciudad_usuario": "Bogotá",
        },
    )

    assert response.status_code == 422


def test_disponibilidad_rechaza_longitud_fuera_de_rango(client: TestClient, db_session) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="LNGRANGE")

    response = client.post(
        "/api/v1/disponibilidad",
        json={
            "medicamento_id": medicamento_id,
            "lat_usuario": 4.65,
            "lng_usuario": -200.0,  # fuera de -180/180
            "ciudad_usuario": "Bogotá",
        },
    )

    assert response.status_code == 422


def test_actualizar_estado_domicilio_rechaza_lat_actual_fuera_de_rango(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="PATCHLAT")
    with ips_db(1) as db:
        orden = OrdenMedica(
            usuario_cedula="1010101010",
            archivo_url="https://ejemplo.test/formula.pdf",
            medicamento_id=medicamento_id,
            estado=EstadoOrden.APROBADA,
        )
        db.add(orden)
        punto = PuntoVenta(nombre="Sede", ciudad="Bogotá", direccion="Calle 1", lat=4.65, lng=-74.06)
        db.add(punto)
        db.commit()
        db.refresh(orden)
        db.refresh(punto)
        orden_id, punto_id = orden.id, punto.id

    paciente = token_factory(cedula="1010101010", ips_id=1)
    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    assert creado.status_code == 201
    domicilio_id = creado.json()["id"]

    from app.models.usuario import RolUsuario

    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    response = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado",
        json={"estado": "en_camino", "lat_actual": 95.0, "lng_actual": -74.06},
        headers=regente,
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# tipo/tamaño del archivo al cargar una orden
# ---------------------------------------------------------------------------

def test_cargar_orden_rechaza_tipo_de_archivo_no_soportado(
    client: TestClient, db_session, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="TIPOBAD")
    paciente = token_factory(cedula="1010101010", ips_id=1)

    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files={"archivo": ("formula.txt", b"no es una imagen ni un pdf", "text/plain")},
        headers=paciente,
    )

    assert response.status_code == 422
    assert "formato" in response.json()["detail"].lower()


def test_cargar_orden_rechaza_archivo_mayor_a_5mb(
    client: TestClient, db_session, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="TAMANOBAD")
    paciente = token_factory(cedula="1010101010", ips_id=1)

    archivo_muy_grande = b"0" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files={"archivo": ("formula.png", archivo_muy_grande, "image/png")},
        headers=paciente,
    )

    assert response.status_code == 413
    assert "5 mb" in response.json()["detail"].lower()


def test_cargar_orden_acepta_imagen_valida_y_la_guarda_como_data_uri(
    client: TestClient, db_session, token_factory
) -> None:
    """Regresion: el cambio de URL externa a archivo subido debe guardar el
    contenido codificado en base64 como "data URI", listo para mostrarse
    directo en el navegador sin depender de almacenamiento externo."""
    medicamento_id = _crear_medicamento(db_session, sufijo="ARCHIVOOK")
    paciente = token_factory(cedula="1010101010", ips_id=1)

    response = client.post(
        "/api/v1/ordenes",
        data={"ips_id": 1, "medicamento_id": medicamento_id},
        files=archivo_formula_prueba(),
        headers=paciente,
    )

    assert response.status_code == 201
    assert response.json()["archivo_url"].startswith("data:image/png;base64,")
