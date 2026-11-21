#!/usr/bin/env python3
"""Lee un .jtl (CSV) generado por perf/jmeter/medicerca_load.jmx y dice si
cada endpoint cumple los umbrales de p95 y tasa de error.

Los umbrales son "por acordar con el equipo" (ver perf/README.md): los
valores por defecto de abajo son un punto de partida razonable para un
prototipo academico, no un SLA real. Se pueden cambiar sin tocar este
script, por linea de comandos.

Uso:
    python3 perf/check_thresholds.py perf/results/baseline.jtl
    python3 perf/check_thresholds.py perf/results/baseline.jtl --p95-ms 800 --error-rate-pct 1
    python3 perf/check_thresholds.py perf/results/rate_limit.jtl --rate-limit-check

Codigo de salida: 0 si todo cumple, 1 si algo no cumple (util en CI).
"""
import argparse
import csv
import sys
from collections import defaultdict


def percentil(valores_ordenados: list[float], p: float) -> float:
    if not valores_ordenados:
        return 0.0
    k = (len(valores_ordenados) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(valores_ordenados) - 1)
    if f == c:
        return valores_ordenados[f]
    return valores_ordenados[f] + (valores_ordenados[c] - valores_ordenados[f]) * (k - f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jtl", help="Ruta al archivo .jtl (CSV) a analizar")
    parser.add_argument("--p95-ms", type=float, default=800.0, help="p95 maximo aceptable, en ms (default: 800, por acordar)")
    parser.add_argument("--error-rate-pct", type=float, default=1.0, help="Tasa de error maxima aceptable, en %% (default: 1, por acordar)")
    parser.add_argument(
        "--rate-limit-check",
        action="store_true",
        help="En vez de p95/error-rate, verifica que hubo al menos un 429 y ningun 5xx (para el escenario 04)",
    )
    args = parser.parse_args()

    try:
        with open(args.jtl, newline="", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"No se encontro el archivo: {args.jtl}", file=sys.stderr)
        print("¿Ya corriste perf/run.sh para este escenario?", file=sys.stderr)
        return 1

    if not filas:
        print(f"{args.jtl} esta vacio: ¿la corrida realmente genero trafico?", file=sys.stderr)
        return 1

    if args.rate_limit_check:
        return _chequeo_rate_limit(filas)
    return _chequeo_umbrales(filas, args.p95_ms, args.error_rate_pct)


def _codigo(fila: dict) -> str:
    return (fila.get("responseCode") or "").strip()


def _chequeo_rate_limit(filas: list[dict]) -> int:
    total = len(filas)
    con_429 = sum(1 for f in filas if _codigo(f) == "429")
    con_5xx = sum(1 for f in filas if _codigo(f).startswith("5"))
    con_2xx_4xx = sum(1 for f in filas if _codigo(f) and _codigo(f)[0] in ("2", "4"))

    print(f"Total de muestras: {total}")
    print(f"  Con 429 (limite excedido): {con_429}")
    print(f"  Con 5xx (NO deberia haber): {con_5xx}")
    print(f"  Con 2xx/4xx (esperado, incluye los 429): {con_2xx_4xx}")

    ok = True
    if con_429 == 0:
        print("FALLO: no se observo ningun 429 -- la rafaga no logro superar el limite de slowapi (¿ratelimit_users/loops muy bajos?).")
        ok = False
    else:
        print(f"OK: se observaron {con_429} respuestas 429, como se esperaba al exceder el limite.")

    if con_5xx > 0:
        print(f"FALLO: se observaron {con_5xx} respuestas 5xx -- el rate limiting no deberia producir errores de servidor.")
        ok = False
    else:
        print("OK: ninguna respuesta 5xx.")

    return 0 if ok else 1


def _chequeo_umbrales(filas: list[dict], p95_max_ms: float, error_rate_max_pct: float) -> int:
    por_label: dict[str, list[dict]] = defaultdict(list)
    for fila in filas:
        por_label[fila.get("label", "(sin etiqueta)")].append(fila)

    timestamps = [int(f["timeStamp"]) for f in filas if f.get("timeStamp", "").isdigit()]
    duracion_s = max((max(timestamps) - min(timestamps)) / 1000.0, 0.001) if timestamps else 0.001

    print(f"Umbrales: p95 <= {p95_max_ms} ms, tasa de error <= {error_rate_max_pct}% (por acordar con el equipo)")
    print(f"Duracion total observada: {duracion_s:.1f} s\n")
    print(f"{'Endpoint':<28} {'n':>6} {'prom(ms)':>10} {'p95(ms)':>10} {'req/s':>8} {'error%':>8}  resultado")
    print("-" * 90)

    todo_ok = True
    for label, muestras in sorted(por_label.items()):
        tiempos = sorted(float(m["elapsed"]) for m in muestras if m.get("elapsed", "").replace(".", "", 1).isdigit())
        n = len(muestras)
        errores = sum(1 for m in muestras if (m.get("success") or "").lower() != "true")
        tasa_error = (errores / n * 100) if n else 0.0
        promedio = sum(tiempos) / len(tiempos) if tiempos else 0.0
        p95 = percentil(tiempos, 95)
        throughput = n / duracion_s

        cumple_p95 = p95 <= p95_max_ms
        cumple_error = tasa_error <= error_rate_max_pct
        resultado = "OK" if (cumple_p95 and cumple_error) else "FALLA"
        if resultado == "FALLA":
            todo_ok = False

        print(f"{label:<28} {n:>6} {promedio:>10.1f} {p95:>10.1f} {throughput:>8.2f} {tasa_error:>7.1f}%  {resultado}")

    print()
    print("TODO CUMPLE" if todo_ok else "HAY ENDPOINTS QUE NO CUMPLEN LOS UMBRALES (ver tabla arriba)")
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
