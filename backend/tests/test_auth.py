from fastapi.testclient import TestClient

from app.config import settings
from app.models.medicamento import CondicionVenta, Medicamento
from tests.conftest import archivo_formula_prueba


def _registro_payload(**cambios: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Ana Prueba",
        "cedula": "1010101010",
        "correo": "ana.prueba@correo.com",
        "password": "ClaveSegura123",
        "ips_id": 1,
    }
    payload.update(cambios)
    return payload


def test_registro_crea_cuenta_no_verificada_y_devuelve_otp_simulado(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=_registro_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["usuario"]["correo"] == "ana.prueba@correo.com"
    assert body["usuario"]["verificado"] is False
    assert body["codigo_demo"].isdigit()
    assert len(body["codigo_demo"]) == 6
    assert body["usuario"]["rol"] == "paciente"


def test_registro_publico_no_permite_autoasignarse_rol_regente(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=_registro_payload(rol="regente"))

    assert response.status_code == 422


def test_registro_con_ips_crea_afiliacion_y_ips_invalidas_son_rechazadas(client: TestClient, db_session) -> None:
    registro = client.post("/api/v1/auth/register", json=_registro_payload())
    assert registro.status_code == 201

    from app.models.ips import AfiliacionUsuario

    afiliacion = db_session.query(AfiliacionUsuario).one()
    assert afiliacion.ips_id == 1
    assert afiliacion.activa is True

    invalida = client.post(
        "/api/v1/auth/register",
        json=_registro_payload(cedula="2020202020", correo="otra@correo.com", ips_id=99),
    )
    assert invalida.status_code == 404


def test_verificacion_habilita_login_y_otp_invalido_es_rechazado(client: TestClient) -> None:
    datos = _registro_payload()
    registro = client.post("/api/v1/auth/register", json=datos)
    codigo = registro.json()["codigo_demo"]

    sin_verificar = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": datos["password"]},
    )
    assert sin_verificar.status_code == 403

    invalido = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": "000000"},
    )
    assert invalido.status_code == 400

    verificacion = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": codigo},
    )
    assert verificacion.status_code == 200
    assert verificacion.json()["verificado"] is True

    login = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": datos["password"]},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]


def test_cambio_password_invalida_la_clave_anterior(client: TestClient) -> None:
    datos = _registro_payload()
    registro = client.post("/api/v1/auth/register", json=datos)
    client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": registro.json()["codigo_demo"]},
    )

    solicitud = client.post(
        "/api/v1/auth/solicitar-cambio-password",
        json={"correo": datos["correo"]},
    )
    assert solicitud.status_code == 200
    assert solicitud.json()["codigo_demo"]

    cambio = client.post(
        "/api/v1/auth/confirmar-cambio-password",
        json={
            "correo": datos["correo"],
            "codigo": solicitud.json()["codigo_demo"],
            "nueva_password": "NuevaClave456",
        },
    )
    assert cambio.status_code == 200

    clave_anterior = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": datos["password"]},
    )
    assert clave_anterior.status_code == 401

    clave_nueva = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": "NuevaClave456"},
    )
    assert clave_nueva.status_code == 200


def test_registro_rechaza_password_debil(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=_registro_payload(password="123456"))
    assert response.status_code == 422

    response = client.post("/api/v1/auth/register", json=_registro_payload(password="minusculas123"))
    assert response.status_code == 422

    response = client.post("/api/v1/auth/register", json=_registro_payload(password="SoloLetras"))
    assert response.status_code == 422


def test_otp_se_bloquea_tras_varios_intentos_fallidos(client: TestClient) -> None:
    datos = _registro_payload()
    registro = client.post("/api/v1/auth/register", json=datos)
    codigo_real = registro.json()["codigo_demo"]

    for _ in range(5):
        fallo = client.post(
            "/api/v1/auth/verificar-registro",
            json={"correo": datos["correo"], "codigo": "000000"},
        )
        assert fallo.status_code == 400

    # Se agotaron los intentos: incluso el código correcto ya no sirve.
    agotado = client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": codigo_real},
    )
    assert agotado.status_code == 400


def test_login_se_bloquea_tras_varios_intentos_fallidos(client: TestClient) -> None:
    datos = _registro_payload()
    registro = client.post("/api/v1/auth/register", json=datos)
    client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": registro.json()["codigo_demo"]},
    )

    for _ in range(5):
        fallo = client.post(
            "/api/v1/auth/login",
            json={"correo": datos["correo"], "password": "ClaveIncorrecta1"},
        )
        assert fallo.status_code == 401

    # Ya bloqueado: ni siquiera la contraseña correcta pasa hasta que expire el bloqueo.
    bloqueado = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": datos["password"]},
    )
    assert bloqueado.status_code == 429


def test_admin_crea_regente_con_clave_valida_y_rechaza_clave_invalida(client: TestClient) -> None:
    sin_clave = client.post(
        "/api/v1/admin/regentes",
        json={
            "nombre": "Regente Nuevo",
            "cedula": "999999999",
            "correo": "regente.nuevo@correo.com",
            "password": "ClaveSegura123",
        },
    )
    assert sin_clave.status_code == 422  # header requerido ausente

    clave_incorrecta = client.post(
        "/api/v1/admin/regentes",
        headers={"X-Admin-Key": "clave-equivocada"},
        json={
            "nombre": "Regente Nuevo",
            "cedula": "999999999",
            "correo": "regente.nuevo@correo.com",
            "password": "ClaveSegura123",
        },
    )
    assert clave_incorrecta.status_code == 401

    creado = client.post(
        "/api/v1/admin/regentes",
        headers={"X-Admin-Key": settings.admin_key},
        json={
            "nombre": "Regente Nuevo",
            "cedula": "999999999",
            "correo": "regente.nuevo@correo.com",
            "password": "ClaveSegura123",
            "ips_id": 1,
        },
    )
    assert creado.status_code == 201
    body = creado.json()
    assert body["rol"] == "regente"
    assert body["verificado"] is True

    login = client.post(
        "/api/v1/auth/login",
        json={"correo": "regente.nuevo@correo.com", "password": "ClaveSegura123"},
    )
    assert login.status_code == 200


def test_logout_revoca_el_token_y_ya_no_sirve_para_endpoints_protegidos(
    client: TestClient, db_session, token_factory
) -> None:
    medicamento = Medicamento(
        nombre_generico="Medicamento Logout",
        nombre_comercial="Comercial Logout",
        dosis="500 mg",
        presentacion="Tabletas x 10",
        condicion_venta=CondicionVenta.OTC,
        control_especial=False,
        registro_sanitario="INVIMA-LOGOUT-001",
        indicaciones_uso="Tomar segun indicacion medica.",
        cantidad_por_entrega="1 caja",
        duracion_tratamiento_dias=30,
    )
    db_session.add(medicamento)
    db_session.commit()
    db_session.refresh(medicamento)

    headers = token_factory(ips_id=1)
    payload_orden = {"ips_id": 1, "medicamento_id": medicamento.id}

    # Un endpoint protegido funciona antes del logout.
    antes = client.post("/api/v1/ordenes", headers=headers, data=payload_orden, files=archivo_formula_prueba())
    assert antes.status_code != 401

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204

    despues = client.post("/api/v1/ordenes", headers=headers, data=payload_orden, files=archivo_formula_prueba())
    assert despues.status_code == 401

    # Idempotente: repetir logout con el mismo token (ya revocado) no debe explotar.
    logout_otra_vez = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_otra_vez.status_code == 204


def test_logout_sin_token_no_falla(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401  # oauth2_scheme exige el header


def test_login_correo_inexistente_tarda_similar_a_password_incorrecta(client: TestClient) -> None:
    """Defensa contra timing attack: si el correo no existe, login() debe pagar
    igual el costo de bcrypt (hash señuelo) que cuando el correo existe pero la
    contraseña es incorrecta. Si alguien vuelve a poner un `if usuario is None:
    return 401` temprano sin pasar por bcrypt, este test debe notarlo."""
    import time

    datos = _registro_payload()
    registro = client.post("/api/v1/auth/register", json=datos)
    client.post(
        "/api/v1/auth/verificar-registro",
        json={"correo": datos["correo"], "codigo": registro.json()["codigo_demo"]},
    )

    inicio = time.perf_counter()
    correo_existente_password_mala = client.post(
        "/api/v1/auth/login",
        json={"correo": datos["correo"], "password": "ClaveIncorrecta1"},
    )
    duracion_existente = time.perf_counter() - inicio
    assert correo_existente_password_mala.status_code == 401

    inicio = time.perf_counter()
    correo_inexistente = client.post(
        "/api/v1/auth/login",
        json={"correo": "no.existe.jamas@correo.com", "password": "ClaveIncorrecta1"},
    )
    duracion_inexistente = time.perf_counter() - inicio
    assert correo_inexistente.status_code == 401

    # No comparamos milisegundos exactos (sería un test frágil en CI), solo que
    # la rama de "correo inexistente" no sea drásticamente más rápida (lo cual
    # delataría que se saltó el hash bcrypt).
    assert duracion_inexistente > duracion_existente * 0.5


def test_me_devuelve_la_identidad_del_usuario_autenticado(client: TestClient, token_factory) -> None:
    from app.models.usuario import RolUsuario

    headers = token_factory(nombre="Regente Uno", rol=RolUsuario.REGENTE, ips_id=1)

    respuesta = client.get("/api/v1/auth/me", headers=headers)

    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["nombre"] == "Regente Uno"
    assert body["rol"] == "regente"
    assert body["ips_id"] == 1


def test_me_sin_token_devuelve_401(client: TestClient) -> None:
    respuesta = client.get("/api/v1/auth/me")
    assert respuesta.status_code == 401


def test_health_reporta_las_cuatro_bases_de_datos(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["bases_de_datos"].keys()) == {"central", "demo_ips_1", "demo_ips_2", "demo_ips_3"}
    assert all(body["bases_de_datos"].values())
