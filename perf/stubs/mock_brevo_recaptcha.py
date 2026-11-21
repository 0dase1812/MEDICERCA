#!/usr/bin/env python3
"""Stub HTTP local para simular fallas de Brevo (envio de correo) y de
reCAPTCHA (verificacion de captcha) bajo carga, para HU-S3-10.

No llama a ningun servicio real: solo responde localmente segun --mode.
Solo depende de la libreria estandar de Python.

IMPORTANTE (bloqueo documentado): para que el backend realmente hable con
este stub en vez de con Google/Brevo, captcha.py y email.py tendrian que
leer la URL desde `settings` en lugar de la constante hardcodeada que usan
hoy (ver perf/README.md, seccion "Hallazgos" y HU-S3-10). Ese cambio se
dejo SOLO DOCUMENTADO, sin aplicar, a pedido explicito del usuario. Mientras
no se aplique, este stub sirve para probarlo de forma aislada (con curl o
con el escenario 05 del plan de JMeter si se activa manualmente), pero el
backend en su estado actual no lo usara automaticamente.

Uso:
    python3 perf/stubs/mock_brevo_recaptcha.py --port 9999 --mode slow --delay-seconds 8
    python3 perf/stubs/mock_brevo_recaptcha.py --port 9999 --mode error
    python3 perf/stubs/mock_brevo_recaptcha.py --port 9999 --mode timeout --delay-seconds 30
    python3 perf/stubs/mock_brevo_recaptcha.py --port 9999 --mode ok

Modos:
    ok      - responde de inmediato como si el servicio real funcionara bien.
    slow    - responde bien, pero tras `--delay-seconds` (simula latencia alta
              sin llegar a disparar el timeout del cliente: usar un valor menor
              al timeout configurado en captcha.py/email.py, ej. 3-4s).
    timeout - duerme mas que el timeout del cliente (5s para reCAPTCHA, 10s
              para Brevo) para forzar que el cliente corte por timeout.
    error   - responde 500 de inmediato (servicio externo caido/con error).
    down    - no abre el puerto (listo para usarse como "no levantar el stub"
              y que el cliente vea connection refused).
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class StubHandler(BaseHTTPRequestHandler):
    mode = "ok"
    delay_seconds = 0.0

    def _responder_recaptcha_ok(self) -> bytes:
        return json.dumps({"success": True, "score": 0.9, "action": "submit"}).encode("utf-8")

    def _responder_brevo_ok(self) -> bytes:
        return json.dumps({"messageId": "stub-message-id"}).encode("utf-8")

    def _cuerpo_ok_segun_ruta(self) -> bytes:
        if "siteverify" in self.path:
            return self._responder_recaptcha_ok()
        return self._responder_brevo_ok()

    def do_POST(self):  # noqa: N802 - nombre impuesto por BaseHTTPRequestHandler
        largo = int(self.headers.get("Content-Length", 0) or 0)
        if largo:
            self.rfile.read(largo)  # drenar el cuerpo de la peticion, sin usarlo

        if self.mode == "slow":
            time.sleep(self.delay_seconds)
            cuerpo = self._cuerpo_ok_segun_ruta()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(cuerpo)
        elif self.mode == "timeout":
            time.sleep(self.delay_seconds)
            # Si el cliente ya cerro la conexion por su propio timeout, esto
            # falla en silencio; es justo el comportamiento que queremos probar.
            try:
                cuerpo = self._cuerpo_ok_segun_ruta()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(cuerpo)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.mode == "error":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "stub: fallo simulado del servicio externo"}).encode("utf-8"))
        else:  # "ok"
            cuerpo = self._cuerpo_ok_segun_ruta()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(cuerpo)

    def log_message(self, format, *args):  # noqa: A002 - firma impuesta por la clase base
        print(f"[stub:{self.mode}] {self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--mode", choices=["ok", "slow", "timeout", "error", "down"], default="ok")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=8.0,
        help="Segundos de espera para los modos 'slow' y 'timeout' (default: 8)",
    )
    args = parser.parse_args()

    if args.mode == "down":
        print("Modo 'down': no se levanta ningun servidor a proposito (simula el servicio caído).")
        print("Deja esta terminal abierta o simplemente no ejecutes este script para ese escenario.")
        return

    StubHandler.mode = args.mode
    StubHandler.delay_seconds = args.delay_seconds

    servidor = ThreadingHTTPServer(("0.0.0.0", args.port), StubHandler)
    print(f"Stub Brevo/reCAPTCHA escuchando en 0.0.0.0:{args.port} (modo={args.mode}, delay={args.delay_seconds}s)")
    print("Rutas: cualquier POST se responde igual; se distingue reCAPTCHA de Brevo solo si la URL trae 'siteverify'.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
