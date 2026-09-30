from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models_ips import EstadoOrden, OrdenMedica, PuntoVenta


def _crear_medicamentos_legales(db_session) -> dict[str, int]:
    medicamentos = {
        "rx": Medicamento(
            nombre_generico="Amoxicilina",
            nombre_comercial="Amoxicilina Prueba",
            dosis="500 mg",
            presentacion="Cápsulas x 10",
            condicion_venta=CondicionVenta.RX,
            control_especial=False,
            registro_sanitario="INVIMA-RX-001",
            indicaciones_uso="Tomar segun indicacion medica.",
            cantidad_por_entrega="1 caja",
            duracion_tratamiento_dias=30,
        ),
        "control": Medicamento(
            nombre_generico="Medicamento Controlado",
            nombre_comercial="Controlado Prueba",
            dosis="10 mg",
            presentacion="Tabletas x 10",
            condicion_venta=CondicionVenta.RX,
            control_especial=True,
            registro_sanitario="INVIMA-CTRL-001",
            indicaciones_uso="Tomar segun indicacion medica.",
            cantidad_por_entrega="1 caja",
            duracion_tratamiento_dias=30,
        ),
    }
    db_session.add_all(medicamentos.values())
    db_session.flush()
    ids = {nombre: medicamento.id for nombre, medicamento in medicamentos.items()}
    db_session.commit()
    return ids


def _crear_orden(ips_db, estado: EstadoOrden, medicamento_id: int) -> dict[str, int]:
    with ips_db(1) as db:
        punto = PuntoVenta(
            nombre="Sede origen",
            ciudad="Bogotá",
            direccion="Calle 1 # 2-3",
            lat=4.6500,
            lng=-74.0600,
        )
        orden = OrdenMedica(
            usuario_cedula="1010101010",
            archivo_url="https://ejemplo.test/formula.pdf",
            medicamento_id=medicamento_id,
            estado=estado,
        )
        db.add_all([punto, orden])
        db.commit()
        db.refresh(punto)
        db.refresh(orden)
        return {"punto_origen_id": punto.id, "orden_id": orden.id}


def test_medicamento_rx_exige_orden_aprobada(client: TestClient, db_session, ips_db, token_factory) -> None:
    medicamentos = _crear_medicamentos_legales(db_session)
    orden = _crear_orden(ips_db, EstadoOrden.PENDIENTE, medicamentos["rx"])

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "medicamento_id": medicamentos["rx"], **orden},
        headers=token_factory(cedula="1010101010"),
    )

    assert response.status_code == 422
    assert "fórmula médica aprobada" in response.json()["detail"].lower()


def test_medicamento_rx_con_orden_aprobada_permite_domicilio(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamentos = _crear_medicamentos_legales(db_session)
    orden = _crear_orden(ips_db, EstadoOrden.APROBADA, medicamentos["rx"])

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "medicamento_id": medicamentos["rx"], **orden},
        headers=token_factory(cedula="1010101010"),
    )

    assert response.status_code == 201
    assert response.json()["estado"] == "confirmado"


def test_control_especial_nunca_permite_domicilio(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamentos = _crear_medicamentos_legales(db_session)
    orden = _crear_orden(ips_db, EstadoOrden.APROBADA, medicamentos["control"])

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "medicamento_id": medicamentos["control"], **orden},
        headers=token_factory(cedula="1010101010"),
    )

    assert response.status_code == 422
    assert "control especial" in response.json()["detail"].lower()


def test_domicilio_no_permite_medicamento_distinto_al_amparado_por_la_orden(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    """Una orden aprobada para un medicamento X no debe servir para pedir Y a domicilio."""
    medicamentos = _crear_medicamentos_legales(db_session)
    otro_rx = Medicamento(
        nombre_generico="Loratadina",
        nombre_comercial="Loratadina Prueba",
        dosis="10 mg",
        presentacion="Tabletas x 10",
        condicion_venta=CondicionVenta.RX,
        control_especial=False,
        registro_sanitario="INVIMA-RX-002",
        indicaciones_uso="Tomar segun indicacion medica.",
        cantidad_por_entrega="1 caja",
        duracion_tratamiento_dias=30,
    )
    db_session.add(otro_rx)
    db_session.commit()

    orden = _crear_orden(ips_db, EstadoOrden.APROBADA, medicamentos["rx"])

    response = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "medicamento_id": otro_rx.id, **orden},
        headers=token_factory(cedula="1010101010"),
    )

    assert response.status_code == 422
    assert "no coincide" in response.json()["detail"].lower()
