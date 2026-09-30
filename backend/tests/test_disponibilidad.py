from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models_ips import Inventario, PuntoVenta


@pytest.fixture
def catalogo_e_inventario(db_session, ips_db) -> dict[str, int]:
    """Siembra inventarios distintos en cada IPS para probar la agregación."""
    medicamentos = {
        "otc": Medicamento(
            nombre_generico="Acetaminofén",
            nombre_comercial="Acetaminofén Prueba",
            dosis="500 mg",
            presentacion="Tabletas x 10",
            condicion_venta=CondicionVenta.OTC,
            control_especial=False,
            registro_sanitario="INVIMA-OTC-001",
            indicaciones_uso="Tomar segun indicacion medica.",
            cantidad_por_entrega="1 caja",
            duracion_tratamiento_dias=30,
        ),
        "agotado": Medicamento(
            nombre_generico="Loratadina",
            nombre_comercial="Loratadina Prueba",
            dosis="10 mg",
            presentacion="Tabletas x 10",
            condicion_venta=CondicionVenta.OTC,
            control_especial=False,
            registro_sanitario="INVIMA-OTC-002",
            indicaciones_uso="Tomar segun indicacion medica.",
            cantidad_por_entrega="1 caja",
            duracion_tratamiento_dias=30,
        ),
    }
    db_session.add_all(medicamentos.values())
    db_session.flush()
    ids = {nombre: medicamento.id for nombre, medicamento in medicamentos.items()}
    db_session.commit()

    sedes = {
        1: ("Sede Norte", "Bogotá", "Calle 72 # 10-20", 4.6486, -74.0600, 12, date(2026, 8, 18)),
        2: ("Sede Sur", "Bogotá", "Calle 170 # 7-10", 4.7450, -74.0300, 4, date(2026, 8, 14)),
        3: ("Sede Medellín", "Medellín", "Carrera 43 # 8-50", 6.2088, -75.5675, 8, date(2026, 8, 20)),
    }
    for ips_id, (nombre, ciudad, direccion, lat, lng, cantidad_otc, reabastecimiento) in sedes.items():
        with ips_db(ips_id) as db:
            punto = PuntoVenta(nombre=nombre, ciudad=ciudad, direccion=direccion, lat=lat, lng=lng)
            db.add(punto)
            db.flush()
            db.add_all(
                [
                    Inventario(punto_id=punto.id, medicamento_id=ids["otc"], cantidad=cantidad_otc),
                    Inventario(
                        punto_id=punto.id,
                        medicamento_id=ids["agotado"],
                        cantidad=0,
                        fecha_reabastecimiento=reabastecimiento,
                    ),
                ]
            )
            db.commit()

    return ids


def test_disponibilidad_agrega_las_tres_ips_y_prioriza_cercania(
    client: TestClient, catalogo_e_inventario: dict[str, int]
) -> None:
    response = client.post(
        "/api/v1/disponibilidad",
        json={
            "medicamento_id": catalogo_e_inventario["otc"],
            "lat_usuario": 4.6490,
            "lng_usuario": -74.0602,
            "ciudad_usuario": "Bogotá",
        },
    )

    assert response.status_code == 200
    resultados = response.json()
    assert [resultado["ips_id"] for resultado in resultados] == [1, 2, 3]
    assert [resultado["nivel"] for resultado in resultados] == [
        "punto_mas_cercano",
        "otro_punto_ciudad",
        "otra_ciudad",
    ]
    assert resultados[0]["cantidad"] == 12


def test_comparacion_de_ciudad_ignora_tildes_y_mayusculas(
    client: TestClient, catalogo_e_inventario: dict[str, int]
) -> None:
    """El seed real del proyecto guarda 'Bogota' sin tilde (ver app/seed.py),
    pero un usuario real escribe 'Bogotá' con tilde. Sin normalizar, esa
    diferencia hacía que CADA resultado cayera en 'otra_ciudad' en vez de
    'punto_mas_cercano'/'otro_punto_ciudad', aunque la sede sí estuviera en la
    misma ciudad."""
    response = client.post(
        "/api/v1/disponibilidad",
        json={
            "medicamento_id": catalogo_e_inventario["otc"],
            "lat_usuario": 4.6490,
            "lng_usuario": -74.0602,
            "ciudad_usuario": "BOGOTA",
        },
    )

    assert response.status_code == 200
    resultados = response.json()
    assert [resultado["nivel"] for resultado in resultados] == [
        "punto_mas_cercano",
        "otro_punto_ciudad",
        "otra_ciudad",
    ]


def test_sin_stock_informa_reabastecimiento_mas_proximo(
    client: TestClient, catalogo_e_inventario: dict[str, int]
) -> None:
    response = client.post(
        "/api/v1/disponibilidad",
        json={
            "medicamento_id": catalogo_e_inventario["agotado"],
            "lat_usuario": 4.6490,
            "lng_usuario": -74.0602,
            "ciudad_usuario": "Bogotá",
        },
    )

    assert response.status_code == 200
    resultados = response.json()
    assert [resultado["nivel"] for resultado in resultados] == ["no_disponible"] * 3
    assert resultados[0]["ips_id"] == 2
    assert resultados[0]["fecha_reabastecimiento"] == "2026-08-14"
