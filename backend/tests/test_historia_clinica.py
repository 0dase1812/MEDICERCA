from datetime import date

from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models.usuario import RolUsuario
from app.models_ips import HistoriaClinica, PrescripcionActiva


def test_historia_clinica_se_busca_por_cedula_en_la_ips_del_usuario(
    client: TestClient, ips_db, usuario_factory
) -> None:
    usuario = usuario_factory(cedula="1011097239", ips_id=1)
    with ips_db(1) as db:
        historia = HistoriaClinica(
            cedula=usuario["cedula"],
            diagnostico_simulado="Hipertensión arterial controlada",
        )
        db.add(historia)
        db.flush()
        db.add(
            PrescripcionActiva(
                historia_id=historia.id,
                medicamento_id=987,
                fecha_formula=date(2026, 8, 1),
                vigente=True,
            )
        )
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"correo": usuario["correo"], "password": usuario["password"]},
    )
    assert login.status_code == 200

    response = client.get(
        "/api/v1/historia-clinica/mia",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    historia = response.json()
    assert historia["ips_id"] == 1
    assert historia["diagnostico_simulado"] == "Hipertensión arterial controlada"
    assert historia["prescripciones"] == [
        {"id": 1, "medicamento_id": 987, "fecha_formula": "2026-08-01", "vigente": True}
    ]


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


def test_regente_crea_historia_clinica_y_el_paciente_la_puede_ver(
    client: TestClient, db_session, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="HCNUEVA")
    paciente = token_factory(cedula="6060606060", ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    creado = client.post(
        "/api/v1/historia-clinica/1",
        json={
            "cedula_paciente": "6060606060",
            "diagnostico_simulado": "Rinitis alérgica",
            "medicamento_ids": [medicamento_id],
        },
        headers=regente,
    )
    assert creado.status_code == 201
    assert creado.json()["diagnostico_simulado"] == "Rinitis alérgica"
    assert len(creado.json()["prescripciones"]) == 1
    assert creado.json()["prescripciones"][0]["medicamento_id"] == medicamento_id

    vista_paciente = client.get("/api/v1/historia-clinica/mia", headers=paciente)
    assert vista_paciente.status_code == 200
    assert vista_paciente.json()["diagnostico_simulado"] == "Rinitis alérgica"


def test_regente_actualiza_diagnostico_existente_en_vez_de_duplicarlo(
    client: TestClient, db_session, token_factory
) -> None:
    paciente = token_factory(cedula="7070707070", ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": "7070707070", "diagnostico_simulado": "Diagnóstico inicial"},
        headers=regente,
    )
    actualizado = client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": "7070707070", "diagnostico_simulado": "Diagnóstico corregido"},
        headers=regente,
    )
    assert actualizado.status_code == 201
    assert actualizado.json()["diagnostico_simulado"] == "Diagnóstico corregido"

    vista_paciente = client.get("/api/v1/historia-clinica/mia", headers=paciente)
    assert vista_paciente.json()["diagnostico_simulado"] == "Diagnóstico corregido"


def test_paciente_no_puede_registrar_historia_clinica(client: TestClient, token_factory) -> None:
    paciente = token_factory(cedula="8080808080", ips_id=1)
    response = client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": "8080808080", "diagnostico_simulado": "Algo"},
        headers=paciente,
    )
    assert response.status_code == 403


def test_regente_no_puede_registrar_historia_para_paciente_de_otra_ips(
    client: TestClient, token_factory
) -> None:
    token_factory(cedula="9090909090", ips_id=2)
    regente_ips1 = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    response = client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": "9090909090", "diagnostico_simulado": "Algo"},
        headers=regente_ips1,
    )
    assert response.status_code == 403


def test_registrar_historia_clinica_con_medicamento_inexistente_devuelve_404(
    client: TestClient, token_factory
) -> None:
    token_factory(cedula="1212121212", ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    response = client.post(
        "/api/v1/historia-clinica/1",
        json={
            "cedula_paciente": "1212121212",
            "diagnostico_simulado": "Algo",
            "medicamento_ids": [999999],
        },
        headers=regente,
    )
    assert response.status_code == 404
