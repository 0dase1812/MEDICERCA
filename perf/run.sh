#!/usr/bin/env bash
# Ejecuta el plan de JMeter de MediCerca en modo no-GUI para un escenario.
#
# Uso:
#   perf/run.sh <escenario> [propiedades -J adicionales...]
#
# Escenarios: baseline | spike | stress | rate_limit | all
#
# Ejemplos:
#   perf/run.sh baseline
#   perf/run.sh baseline -Jhost=staging.medicerca.example -Jport=443 -Jprotocol=https
#   perf/run.sh spike -Jspike_peak_users=300
#   perf/run.sh rate_limit
#
# Nada de usuarios, host, puerto ni duracion esta fijo aqui: todo son
# propiedades -J con valores por defecto definidos dentro del .jmx (ver
# perf/README.md para la lista completa). Este script solo decide, segun el
# escenario pedido, que otros grupos de hilos del mismo plan quedan en 0
# usuarios para no generarles trafico.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JMX="$SCRIPT_DIR/jmeter/medicerca_load.jmx"
RESULTS_DIR="$SCRIPT_DIR/results"

ESCENARIO="${1:-}"
shift || true
PROPIEDADES_EXTRA=("$@")

if [[ -z "$ESCENARIO" ]]; then
  echo "Uso: perf/run.sh <baseline|spike|stress|rate_limit|all> [-Jpropiedad=valor ...]" >&2
  exit 1
fi

if ! command -v jmeter >/dev/null 2>&1; then
  echo "No se encontro 'jmeter' en el PATH. Ver perf/README.md (seccion Requisitos) para instalarlo." >&2
  exit 1
fi

mkdir -p "$RESULTS_DIR"

# Por defecto cada grupo de hilos corre con los valores por defecto del
# .jmx. Para aislar un escenario, los demas grupos se ponen en 0 usuarios
# (no se "deshabilitan": JMeter no permite eso por propiedad, pero un grupo
# con 0 hilos no genera ninguna peticion, que es equivalente en la practica).
APAGAR_BASELINE=(-Jbaseline_users=0)
APAGAR_SPIKE=(-Jspike_floor_users=0 -Jspike_peak_users=0)
APAGAR_STRESS=(-Jstress_step1_users=0 -Jstress_step2_users=0 -Jstress_step3_users=0 -Jstress_step4_users=0)
APAGAR_RATE_LIMIT=(-Jratelimit_users=0)

PROPS=(-Jscenario="$ESCENARIO")

case "$ESCENARIO" in
  baseline)
    PROPS+=("${APAGAR_SPIKE[@]}" "${APAGAR_STRESS[@]}" "${APAGAR_RATE_LIMIT[@]}")
    ;;
  spike)
    PROPS+=("${APAGAR_BASELINE[@]}" "${APAGAR_STRESS[@]}" "${APAGAR_RATE_LIMIT[@]}")
    ;;
  stress)
    PROPS+=("${APAGAR_BASELINE[@]}" "${APAGAR_SPIKE[@]}" "${APAGAR_RATE_LIMIT[@]}")
    ;;
  rate_limit)
    PROPS+=("${APAGAR_BASELINE[@]}" "${APAGAR_SPIKE[@]}" "${APAGAR_STRESS[@]}")
    ;;
  all)
    # No se apaga nada: los 4 escenarios corren juntos, tal como estan
    # definidos en el .jmx (util solo para una corrida de humo corta).
    ;;
  *)
    echo "Escenario desconocido: '$ESCENARIO'. Usa baseline, spike, stress, rate_limit o all." >&2
    exit 1
    ;;
esac

JTL="$RESULTS_DIR/${ESCENARIO}.jtl"
REPORTE_DIR="$RESULTS_DIR/${ESCENARIO}_html"
rm -rf "$REPORTE_DIR"

echo "Escenario: $ESCENARIO"
echo "Resultados: $JTL"
echo "Reporte HTML: $REPORTE_DIR"
echo

jmeter -n \
  -t "$JMX" \
  "${PROPS[@]}" \
  "${PROPIEDADES_EXTRA[@]}" \
  -l "$JTL" \
  -e -o "$REPORTE_DIR"

echo
echo "Listo. Abre $REPORTE_DIR/index.html para el reporte, o corre:"
echo "  python3 perf/check_thresholds.py $JTL"
