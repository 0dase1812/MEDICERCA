#!/usr/bin/env python3
"""Crea y verifica los usuarios de perf/data/usuarios_prueba.csv contra un
entorno de MediCerca en ejecucion (local o de pruebas), para que el plan de
JMeter (perf/jmeter/medicerca_load.jmx) pueda loguearse con ellos.

Solo depende de la libreria estandar de Python (sin requests/locust/etc),
para no agregar dependencias nuevas al proyecto solo por esto.

Requiere EMAIL_MODO=simulado en el backend objetivo (el valor por defecto en
.env.example): asi el codigo de verificacion viaja en la respuesta de la API
(`codigo_demo`) en vez de enviarse por correo real. Si el entorno usa
EMAIL_MODO=real, este script no puede verificar las cuentas solo: avisa y
hay que completar el codigo a mano.

Uso:
    python3 perf/data/crear_usuarios_prueba.py --host localhost --port 8000
"""
import argparse
import csv
import json
import sys
import urllib.error
import urllib.request


def post(base_url: str, path: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url + path,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except urllib.error.URLError as exc:
        print(f"  ERROR de red hablando con {base_url}: {exc}", file=sys.stderr)
        return 0, {}


def asegurar_usuario(base_url: str, fila: dict) -> str:
    correo = fila["correo"]
    password = fila["password"]

    status, cuerpo = post(
        base_url,
        "/api/v1/auth/register",
        {
            "nombre": fila["nombre"],
            "cedula": fila["cedula"],
            "correo": correo,
            "password": password,
        },
    )

    if status == 201:
        codigo = cuerpo.get("codigo_demo")
        if not codigo:
            return (
                "creado, pero sin codigo_demo (EMAIL_MODO no es 'simulado'): "
                "verifica la cuenta a mano con el codigo que llegue por correo"
            )
        status_v, cuerpo_v = post(
            base_url,
            "/api/v1/auth/verificar-registro",
            {"correo": correo, "codigo": codigo},
        )
        if status_v == 200:
            return "creado y verificado"
        return f"creado, pero la verificacion fallo ({status_v}): {cuerpo_v}"

    if status == 400:
        # Ya existe (correo o cedula). Primero confirmamos si ya esta
        # operativo con un login; si no, intentamos reenviar un codigo.
        status_l, _ = post(base_url, "/api/v1/auth/login", {"correo": correo, "password": password})
        if status_l == 200:
            return "ya existia y el login funciona"
        if status_l == 403:
            status_r, cuerpo_r = post(
                base_url,
                "/api/v1/auth/reenviar-codigo",
                {"correo": correo, "proposito": "registro"},
            )
            codigo = cuerpo_r.get("codigo_demo")
            if codigo:
                status_v, cuerpo_v = post(
                    base_url,
                    "/api/v1/auth/verificar-registro",
                    {"correo": correo, "codigo": codigo},
                )
                if status_v == 200:
                    return "ya existia, se reenvio el codigo y quedo verificado"
                return f"ya existia, reenvio ok pero la verificacion fallo ({status_v}): {cuerpo_v}"
            return "ya existia sin verificar, y no se obtuvo codigo_demo: verifica a mano"
        return f"ya existia, pero el login dio {status_l} (revisa la contrasena en el CSV)"

    return f"respuesta inesperada de /register: {status} {cuerpo}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="8000")
    parser.add_argument("--protocol", default="http")
    parser.add_argument(
        "--csv",
        default="perf/data/usuarios_prueba.csv",
        help="Ruta al CSV de usuarios de prueba (default: perf/data/usuarios_prueba.csv)",
    )
    args = parser.parse_args()

    base_url = f"{args.protocol}://{args.host}:{args.port}"
    print(f"Creando/verificando usuarios de prueba contra {base_url} ...\n")

    with open(args.csv, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    for fila in filas:
        resultado = asegurar_usuario(base_url, fila)
        print(f"- {fila['correo']}: {resultado}")

    print("\nListo. Si algun usuario quedo pendiente de verificar a mano, revisa el mensaje de arriba.")


if __name__ == "__main__":
    main()
