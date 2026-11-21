# Ejecuta el plan de JMeter de MediCerca en modo no-GUI para un escenario.
#
# Uso:
#   perf/run.ps1 <escenario> [propiedades -J adicionales...]
#
# Escenarios: baseline | spike | stress | rate_limit | all
#
# Ejemplos:
#   perf/run.ps1 baseline
#   perf/run.ps1 baseline -Jhost=staging.medicerca.example -Jport=443 -Jprotocol=https
#   perf/run.ps1 spike -Jspike_peak_users=300
#   perf/run.ps1 rate_limit
#
# Mismo criterio que run.sh: nada fijo salvo lo que decide, por escenario,
# que otros grupos de hilos quedan en 0 usuarios para no generarles trafico.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("baseline", "spike", "stress", "rate_limit", "all")]
    [string]$Escenario,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PropiedadesExtra
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Jmx = Join-Path $ScriptDir "jmeter\medicerca_load.jmx"
$ResultsDir = Join-Path $ScriptDir "results"

if (-not (Get-Command jmeter -ErrorAction SilentlyContinue)) {
    Write-Error "No se encontro 'jmeter' en el PATH. Ver perf/README.md (seccion Requisitos) para instalarlo."
    exit 1
}

New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

$ApagarBaseline = @("-Jbaseline_users=0")
$ApagarSpike = @("-Jspike_floor_users=0", "-Jspike_peak_users=0")
$ApagarStress = @("-Jstress_step1_users=0", "-Jstress_step2_users=0", "-Jstress_step3_users=0", "-Jstress_step4_users=0")
$ApagarRateLimit = @("-Jratelimit_users=0")

$Props = @("-Jscenario=$Escenario")

switch ($Escenario) {
    "baseline"   { $Props += $ApagarSpike + $ApagarStress + $ApagarRateLimit }
    "spike"      { $Props += $ApagarBaseline + $ApagarStress + $ApagarRateLimit }
    "stress"     { $Props += $ApagarBaseline + $ApagarSpike + $ApagarRateLimit }
    "rate_limit" { $Props += $ApagarBaseline + $ApagarSpike + $ApagarStress }
    "all"        { }
}

$Jtl = Join-Path $ResultsDir "$Escenario.jtl"
$ReporteDir = Join-Path $ResultsDir "${Escenario}_html"
if (Test-Path $ReporteDir) { Remove-Item -Recurse -Force $ReporteDir }

Write-Host "Escenario: $Escenario"
Write-Host "Resultados: $Jtl"
Write-Host "Reporte HTML: $ReporteDir"
Write-Host ""

$ArgumentosCompletos = @("-n", "-t", $Jmx) + $Props + $PropiedadesExtra + @("-l", $Jtl, "-e", "-o", $ReporteDir)
& jmeter @ArgumentosCompletos

Write-Host ""
Write-Host "Listo. Abre $ReporteDir\index.html para el reporte, o corre:"
Write-Host "  python perf/check_thresholds.py $Jtl"
