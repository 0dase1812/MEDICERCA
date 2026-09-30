"""Tests de la paginación (skip/limit + total) agregada en esta sesión a
GET /medicamentos y GET /ips. Ver app/schemas/pagina.py."""
from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento


def _crear_medicamentos(db_session, cantidad: int) -> list[int]:
    medicamentos = [
        Medicamento(
            nombre_generico=f"Medicamento {i}",
            nombre_comercial=f"Comercial {i}",
            dosis="500 mg",
            presentacion="Tabletas x 10",
            condicion_venta=CondicionVenta.OTC,
            control_especial=False,
            registro_sanitario=f"INVIMA-PAG-{i:03d}",
            indicaciones_uso="Tomar segun indicacion medica.",
            cantidad_por_entrega="1 caja",
            duracion_tratamiento_dias=30,
        )
        for i in range(cantidad)
    ]
    db_session.add_all(medicamentos)
    db_session.commit()
    for medicamento in medicamentos:
        db_session.refresh(medicamento)
    return [medicamento.id for medicamento in medicamentos]


def test_medicamentos_pagina_respeta_limit_y_reporta_total(client: TestClient, db_session) -> None:
    _crear_medicamentos(db_session, cantidad=5)

    response = client.get("/api/v1/medicamentos", params={"skip": 0, "limit": 2})

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 5
    assert cuerpo["skip"] == 0
    assert cuerpo["limit"] == 2
    assert len(cuerpo["items"]) == 2


def test_medicamentos_pagina_avanza_con_skip_sin_repetir_ni_saltar(client: TestClient, db_session) -> None:
    ids = _crear_medicamentos(db_session, cantidad=5)

    primera = client.get("/api/v1/medicamentos", params={"skip": 0, "limit": 2}).json()
    segunda = client.get("/api/v1/medicamentos", params={"skip": 2, "limit": 2}).json()
    tercera = client.get("/api/v1/medicamentos", params={"skip": 4, "limit": 2}).json()

    ids_paginados = [item["id"] for pagina in (primera, segunda, tercera) for item in pagina["items"]]
    assert ids_paginados == ids  # sin huecos ni duplicados, en el mismo orden
    assert len(tercera["items"]) == 1  # última página parcial


def test_medicamentos_sin_parametros_usa_valores_por_defecto(client: TestClient, db_session) -> None:
    _crear_medicamentos(db_session, cantidad=3)

    response = client.get("/api/v1/medicamentos")

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["skip"] == 0
    assert cuerpo["limit"] == 50
    assert cuerpo["total"] == 3
    assert len(cuerpo["items"]) == 3


def test_medicamentos_limit_fuera_de_rango_devuelve_422(client: TestClient, db_session) -> None:
    response = client.get("/api/v1/medicamentos", params={"limit": 500})

    assert response.status_code == 422


def test_ips_lista_pagina_con_total(client: TestClient) -> None:
    """El fixture reset_databases siembra 3 IPS activas de demo."""
    response = client.get("/api/v1/ips", params={"limit": 2})

    assert response.status_code == 200
    cuerpo = response.json()
    assert cuerpo["total"] == 3
    assert len(cuerpo["items"]) == 2
