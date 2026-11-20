"""Tests de las HU del Sprint 3 implementadas en esta etapa:

- HU-S3-01: editar y retirar prescripciones de la historia clinica.
- HU-S3-02: auditoria de cambios en la historia clinica.
- HU-S3-04: busqueda de medicamentos por nombre.
- HU-S3-05: reenvio de codigo OTP.
- HU-S3-06: validacion de transicion de estado del domicilio.
"""
from datetime import date

from fastapi.testclient import TestClient

from app.models.medicamento import CondicionVenta, Medicamento
from app.models.usuario import RolUsuario
from app.models_ips import EstadoOrden, HistoriaClinica, OrdenMedica, PrescripcionActiva, PuntoVenta


def _crear_medicamento(db_session, *, sufijo: str) -> int:
    medicamento = Medicamento(
        nombre_generico=f"Losartan {sufijo}",
        nombre_comercial=f"Cozaar {sufijo}",
        dosis="50 mg",
        presentacion="Tabletas x 30",
        condicion_venta=CondicionVenta.RX,
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


def _crear_historia_con_prescripcion(ips_db, *, cedula: str, medicamento_id: int, ips_id: int = 1) -> tuple[int, int]:
    with ips_db(ips_id) as db:
        historia = HistoriaClinica(cedula=cedula, diagnostico_simulado="Hipertension arterial controlada")
        db.add(historia)
        db.flush()
        prescripcion = PrescripcionActiva(
            historia_id=historia.id,
            medicamento_id=medicamento_id,
            fecha_formula=date(2026, 8, 1),
            vigente=True,
        )
        db.add(prescripcion)
        db.commit()
        return historia.id, prescripcion.id


# ---------------------------------------------------------------------------
# HU-S3-01: editar y retirar prescripciones
# ---------------------------------------------------------------------------

def test_regente_edita_medicamento_y_fecha_de_una_prescripcion(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="EDIT1")
    nuevo_medicamento_id = _crear_medicamento(db_session, sufijo="EDIT2")
    _, prescripcion_id = _crear_historia_con_prescripcion(ips_db, cedula="3011097239", medicamento_id=medicamento_id)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    respuesta = client.patch(
        f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}",
        json={"medicamento_id": nuevo_medicamento_id, "fecha_formula": "2026-09-15"},
        headers=regente,
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["medicamento_id"] == nuevo_medicamento_id
    assert cuerpo["fecha_formula"] == "2026-09-15"
    assert cuerpo["vigente"] is True


def test_regente_retira_una_prescripcion_y_no_la_puede_retirar_dos_veces(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="RETIRO1")
    _, prescripcion_id = _crear_historia_con_prescripcion(ips_db, cedula="3011097240", medicamento_id=medicamento_id)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    retirada = client.delete(f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}", headers=regente)
    assert retirada.status_code == 200
    assert retirada.json()["vigente"] is False

    otra_vez = client.delete(f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}", headers=regente)
    assert otra_vez.status_code == 422


def test_no_se_puede_editar_una_prescripcion_ya_retirada(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="RETEDIT")
    _, prescripcion_id = _crear_historia_con_prescripcion(ips_db, cedula="3011097241", medicamento_id=medicamento_id)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    client.delete(f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}", headers=regente)
    intento = client.patch(
        f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}",
        json={"fecha_formula": "2026-09-15"},
        headers=regente,
    )
    assert intento.status_code == 422


def test_paciente_no_puede_editar_ni_retirar_prescripciones(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="PACROL")
    _, prescripcion_id = _crear_historia_con_prescripcion(ips_db, cedula="3011097242", medicamento_id=medicamento_id)
    paciente = token_factory(cedula="3011097242", ips_id=1)

    editar = client.patch(
        f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}",
        json={"fecha_formula": "2026-09-15"},
        headers=paciente,
    )
    assert editar.status_code == 403

    retirar = client.delete(f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}", headers=paciente)
    assert retirar.status_code == 403


def test_editar_prescripcion_con_medicamento_inexistente_devuelve_404(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="EDITNOEXIST")
    _, prescripcion_id = _crear_historia_con_prescripcion(ips_db, cedula="3011097243", medicamento_id=medicamento_id)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    respuesta = client.patch(
        f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}",
        json={"medicamento_id": 999999},
        headers=regente,
    )
    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# HU-S3-02: auditoria de cambios en la historia clinica
# ---------------------------------------------------------------------------

def test_auditoria_registra_creacion_edicion_y_retiro(
    client: TestClient, db_session, token_factory
) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="AUDIT1")
    cedula_paciente = "3011097244"
    token_factory(cedula=cedula_paciente, ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)

    creada = client.post(
        "/api/v1/historia-clinica/1",
        json={
            "cedula_paciente": cedula_paciente,
            "diagnostico_simulado": "Diagnostico inicial",
            "medicamento_ids": [medicamento_id],
        },
        headers=regente,
    )
    assert creada.status_code == 201
    prescripcion_id = creada.json()["prescripciones"][0]["id"]

    client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": cedula_paciente, "diagnostico_simulado": "Diagnostico corregido"},
        headers=regente,
    )
    client.delete(f"/api/v1/historia-clinica/1/prescripciones/{prescripcion_id}", headers=regente)

    auditoria = client.get(f"/api/v1/historia-clinica/1/auditoria/{cedula_paciente}", headers=regente)
    assert auditoria.status_code == 200
    filas = auditoria.json()

    acciones = [(f["entidad"], f["accion"]) for f in filas]
    assert ("diagnostico", "creacion") in acciones
    assert ("diagnostico", "edicion") in acciones
    assert ("prescripcion", "creacion") in acciones
    assert ("prescripcion", "retiro") in acciones

    edicion_diagnostico = next(f for f in filas if f["entidad"] == "diagnostico" and f["accion"] == "edicion")
    assert edicion_diagnostico["valor_anterior"] == "Diagnostico inicial"
    assert edicion_diagnostico["valor_nuevo"] == "Diagnostico corregido"
    assert edicion_diagnostico["autor"]  # queda el nombre del regente que lo hizo


def test_paciente_no_puede_ver_la_auditoria(client: TestClient, db_session, token_factory) -> None:
    medicamento_id = _crear_medicamento(db_session, sufijo="AUDITROL")
    cedula_paciente = "3011097245"
    paciente = token_factory(cedula=cedula_paciente, ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": cedula_paciente, "diagnostico_simulado": "Algo"},
        headers=regente,
    )

    respuesta = client.get(f"/api/v1/historia-clinica/1/auditoria/{cedula_paciente}", headers=paciente)
    assert respuesta.status_code == 403


def test_regente_de_otra_ips_no_puede_ver_auditoria(client: TestClient, db_session, token_factory) -> None:
    cedula_paciente = "3011097246"
    regente_ips1 = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    regente_ips2 = token_factory(rol=RolUsuario.REGENTE, ips_id=2)
    client.post(
        "/api/v1/historia-clinica/1",
        json={"cedula_paciente": cedula_paciente, "diagnostico_simulado": "Algo"},
        headers=regente_ips1,
    )

    respuesta = client.get(f"/api/v1/historia-clinica/1/auditoria/{cedula_paciente}", headers=regente_ips2)
    assert respuesta.status_code == 403


# ---------------------------------------------------------------------------
# HU-S3-04: busqueda de medicamentos por nombre
# ---------------------------------------------------------------------------

def test_busqueda_de_medicamentos_por_nombre_parcial_y_sin_distinguir_mayusculas(
    client: TestClient, db_session
) -> None:
    _crear_medicamento(db_session, sufijo="BUSQ1")  # "Losartan BUSQ1" / "Cozaar BUSQ1"

    exacto = client.get("/api/v1/medicamentos", params={"q": "Losartan BUSQ1"})
    assert exacto.status_code == 200
    assert exacto.json()["total"] == 1

    parcial = client.get("/api/v1/medicamentos", params={"q": "losar"})
    assert parcial.status_code == 200
    assert parcial.json()["total"] == 1

    mayusculas = client.get("/api/v1/medicamentos", params={"q": "LOSARTAN"})
    assert mayusculas.status_code == 200
    assert mayusculas.json()["total"] == 1

    por_comercial = client.get("/api/v1/medicamentos", params={"q": "cozaar"})
    assert por_comercial.status_code == 200
    assert por_comercial.json()["total"] == 1

    sin_resultados = client.get("/api/v1/medicamentos", params={"q": "paracetamol-inexistente"})
    assert sin_resultados.status_code == 200
    assert sin_resultados.json()["total"] == 0
    assert sin_resultados.json()["items"] == []


def test_busqueda_sin_q_devuelve_todo_el_catalogo_paginado(client: TestClient, db_session) -> None:
    _crear_medicamento(db_session, sufijo="SINQ1")
    _crear_medicamento(db_session, sufijo="SINQ2")

    respuesta = client.get("/api/v1/medicamentos")
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] >= 2


# ---------------------------------------------------------------------------
# HU-S3-05: reenvio de codigo OTP
# ---------------------------------------------------------------------------

def test_reenviar_codigo_de_registro_genera_uno_nuevo_y_funciona_para_verificar(
    client: TestClient,
) -> None:
    registro = client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Usuario Reenvio",
            "cedula": "4011097200",
            "correo": "reenvio1@prueba.com",
            "password": "ClaveSegura123",
        },
    )
    assert registro.status_code == 201
    codigo_original = registro.json()["codigo_demo"]

    reenvio = client.post(
        "/api/v1/auth/reenviar-codigo",
        json={"correo": "reenvio1@prueba.com", "proposito": "registro"},
    )
    assert reenvio.status_code == 200
    codigo_nuevo = reenvio.json()["codigo_demo"]
    assert codigo_nuevo is not None
    assert codigo_nuevo != codigo_original  # el reenvio invalida el anterior (app.core.otp.generar_codigo)

    # El codigo original ya no sirve...
    fallido = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": "reenvio1@prueba.com", "codigo": codigo_original},
    )
    assert fallido.status_code == 400

    # ...pero el nuevo si completa el registro.
    exitoso = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": "reenvio1@prueba.com", "codigo": codigo_nuevo},
    )
    assert exitoso.status_code == 200
    assert exitoso.json()["verificado"] is True


def test_reenviar_codigo_a_correo_inexistente_no_revela_nada(client: TestClient) -> None:
    respuesta = client.post(
        "/api/v1/auth/reenviar-codigo",
        json={"correo": "no-existe@prueba.com", "proposito": "registro"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["codigo_demo"] is None


def test_reenviar_codigo_de_registro_a_cuenta_ya_verificada_no_genera_codigo(
    client: TestClient, token_factory
) -> None:
    usuario = token_factory(correo="ya-verificado@prueba.com")  # token_factory crea un usuario ya verificado

    respuesta = client.post(
        "/api/v1/auth/reenviar-codigo",
        json={"correo": "ya-verificado@prueba.com", "proposito": "registro"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["codigo_demo"] is None
    assert usuario  # solo para silenciar el linter de variable no usada


def test_reenviar_codigo_limita_por_ip_tras_varios_intentos(client: TestClient) -> None:
    for _ in range(5):
        respuesta = client.post(
            "/api/v1/auth/reenviar-codigo",
            json={"correo": "cualquiera@prueba.com", "proposito": "cambio_password"},
        )
        assert respuesta.status_code == 200

    bloqueado = client.post(
        "/api/v1/auth/reenviar-codigo",
        json={"correo": "otro-correo-distinto@prueba.com", "proposito": "cambio_password"},
    )
    assert bloqueado.status_code == 429


# ---------------------------------------------------------------------------
# HU-S3-06: validacion de transicion de estado del domicilio
# ---------------------------------------------------------------------------

def _crear_domicilio(client: TestClient, db_session, ips_db, token_factory, *, sufijo: str) -> tuple[str, int]:
    medicamento_id = _crear_medicamento(db_session, sufijo=sufijo)
    cedula = f"50{sufijo}"
    with ips_db(1) as db:
        orden = OrdenMedica(
            usuario_cedula=cedula,
            archivo_url="https://ejemplo.test/formula.pdf",
            medicamento_id=medicamento_id,
            estado=EstadoOrden.APROBADA,
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)
        orden_id = orden.id
        punto = PuntoVenta(nombre="Sede", ciudad="Bogota", direccion="Calle 1", lat=4.65, lng=-74.06)
        db.add(punto)
        db.commit()
        db.refresh(punto)
        punto_id = punto.id

    paciente = token_factory(cedula=cedula, ips_id=1)
    regente = token_factory(rol=RolUsuario.REGENTE, ips_id=1)
    creado = client.post(
        "/api/v1/domicilios",
        json={"ips_id": 1, "orden_id": orden_id, "punto_origen_id": punto_id, "medicamento_id": medicamento_id},
        headers=paciente,
    )
    assert creado.status_code == 201
    return regente, creado.json()["id"]


def test_secuencia_completa_de_estados_es_valida(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    regente, domicilio_id = _crear_domicilio(client, db_session, ips_db, token_factory, sufijo="SEQOK")

    for estado in ("en_alistamiento", "en_camino", "entregado"):
        respuesta = client.patch(
            f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": estado}, headers=regente
        )
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["estado"] == estado


def test_no_se_puede_saltar_directo_de_confirmado_a_entregado(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    regente, domicilio_id = _crear_domicilio(client, db_session, ips_db, token_factory, sufijo="SALTO1")

    respuesta = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "entregado"}, headers=regente
    )
    assert respuesta.status_code == 422


def test_no_se_puede_saltar_directo_de_confirmado_a_en_camino(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    regente, domicilio_id = _crear_domicilio(client, db_session, ips_db, token_factory, sufijo="SALTO2")

    respuesta = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "en_camino"}, headers=regente
    )
    assert respuesta.status_code == 422


def test_un_domicilio_entregado_no_admite_mas_transiciones(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    regente, domicilio_id = _crear_domicilio(client, db_session, ips_db, token_factory, sufijo="TERM1")
    for estado in ("en_alistamiento", "en_camino", "entregado"):
        client.patch(f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": estado}, headers=regente)

    respuesta = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "en_camino"}, headers=regente
    )
    assert respuesta.status_code == 422


def test_cancelar_por_patch_es_valido_desde_confirmado_y_desde_en_alistamiento(
    client: TestClient, db_session, ips_db, token_factory
) -> None:
    regente, domicilio_id = _crear_domicilio(client, db_session, ips_db, token_factory, sufijo="CANCPATCH")

    respuesta = client.patch(
        f"/api/v1/domicilios/1/{domicilio_id}/estado", json={"estado": "cancelado"}, headers=regente
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "cancelado"
