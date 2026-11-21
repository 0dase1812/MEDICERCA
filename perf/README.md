# Pruebas de rendimiento de MediCerca (JMeter)

Plan de JMeter para las historias de usuario del Sprint 3:

- **SCRUM-27 / HU-S3-08** — carga normal (línea base).
- **SCRUM-28 / HU-S3-09** — pico (spike) y estrés escalonado.
- **SCRUM-29 / HU-S3-10** — resiliencia ante fallos de Brevo/reCAPTCHA bajo carga (**bloqueado**, ver más abajo).

Todo apunta siempre a un entorno de pruebas o local con datos ficticios.
**Nunca contra producción, nunca contra Brevo o reCAPTCHA reales.**

## 1. Requisitos

- **Java** 11 o superior (`java -version`).
- **Apache JMeter** 5.6.x. Descárgalo de <https://jmeter.apache.org/download_jmeter.cgi>,
  descomprímelo y agrega su carpeta `bin/` al `PATH` (o usa la ruta completa a `jmeter`/`jmeter.bat`).
- **Plugin "Custom Thread Groups" (jpgc-casutg)**, solo para el escenario de pico (`02 - Pico`),
  que usa un *Ultimate Thread Group*. Instálalo con el
  [JMeter Plugins Manager](https://jmeter-plugins.org/wiki/PluginsManager/) (Options → Plugins
  Manager → pestaña "Available Plugins" → "Custom Thread Groups" → Apply and Restart), o
  manualmente copiando `jmeter-plugins-casutg-*.jar` y sus dependencias (`jmeter-plugins-manager`,
  `jpgc-casutg`) a la carpeta `lib/ext/` de tu instalación de JMeter.
  Los demás escenarios (línea base, estrés escalonado, ráfaga de rate limiting) **no** necesitan
  ningún plugin — usan únicamente Thread Groups nativos.
- **Python 3.11+** solo para `perf/data/crear_usuarios_prueba.py` y `perf/check_thresholds.py`
  (sin dependencias nuevas: solo librería estándar).

> **Nota de esta entrega:** el `.jmx` se construyó y se validó como XML bien formado, y cada
> llamada HTTP que contiene (login, catálogo, disponibilidad, registro) se probó por separado
> con `curl` contra una instancia real del backend corriendo en este mismo entorno de desarrollo
> (ver sección "Qué se validó" más abajo). No se pudo instalar JMeter en el entorno donde se
> generó este plan para correr `jmeter -n` directamente (la descarga desde `apache.org` está
> bloqueada por la política de red de ese entorno) — la primera vez que lo abras en tu máquina,
> ábrelo también en modo GUI una vez para confirmar visualmente el árbol de elementos antes de
> correr nada en modo no-GUI.

## 2. Levantar el entorno de pruebas

Con Docker (como en el resto del proyecto):

```bash
cd backend
cp .env.example .env     # si no existe ya
cd ../infra
docker compose up --build -d
docker compose exec backend python -m app.seed
```

La API queda en `http://localhost:8000` (Swagger en `/docs`). Confirma que está arriba:

```bash
curl http://localhost:8000/api/v1/health
```

Alternativa sin Docker (útil si no tienes Docker disponible, p. ej. en CI): el backend corre
igual de bien con SQLite en vez de Postgres, apuntando `DATABASE_URL`/`DATABASE_URL_IPS_*` a
archivos `sqlite:///...`. Así es como se validó este plan en este entorno — ver el detalle en
la sección "Qué se validó".

### Crear los usuarios de prueba

```bash
pip install -r backend/requirements.txt   # si no lo tienes ya instalado
python3 perf/data/crear_usuarios_prueba.py --host localhost --port 8000
```

Lee `perf/data/usuarios_prueba.csv` (3 usuarios ficticios de plantilla — agrega más filas si
necesitas más concurrencia real de cuentas distintas) y los registra + verifica usando el
`codigo_demo` que la API devuelve cuando `EMAIL_MODO=simulado` (el valor por defecto). Es
idempotente: si ya existen, los deja como están y solo confirma que el login funciona.

## 3. Ejecutar un escenario

```bash
perf/run.sh baseline
perf/run.sh spike
perf/run.sh stress
perf/run.sh rate_limit
```

En Windows (PowerShell):

```powershell
perf\run.ps1 baseline
```

Cada invocación corre **todo** `medicerca_load.jmx`, pero `run.sh`/`run.ps1` ponen en 0 usuarios
los grupos de hilos de los demás escenarios (un grupo con 0 hilos no genera tráfico — JMeter no
permite "deshabilitar por propiedad" un Thread Group completo, así que esto es el equivalente
práctico). Para correr los 4 a la vez (solo tiene sentido en una corrida de humo muy corta):

```bash
perf/run.sh all -Jbaseline_duration_s=30 -Jbaseline_users=5
```

Cualquier propiedad se puede sobreescribir al final del comando, por ejemplo:

```bash
perf/run.sh baseline -Jhost=192.168.1.50 -Jport=8000 -Jbaseline_users=50 -Jbaseline_duration_s=600
```

### Propiedades disponibles (todas con valor por defecto en el `.jmx`)

| Propiedad | Default | Para qué |
|---|---|---|
| `host` | `localhost` | Host del backend |
| `port` | `8000` | Puerto del backend |
| `protocol` | `http` | `http` o `https` |
| `connect_timeout_ms` / `response_timeout_ms` | `5000` / `15000` | Timeouts HTTP del propio JMeter |
| `usuarios_csv` | `perf/data/usuarios_prueba.csv` | CSV de usuarios de prueba |
| `busqueda_termino` / `busqueda_limit` | `` (vacío) / `20` | Filtro `q` y `limit` de `GET /medicamentos` |
| `medicamento_id` | resuelto por el grupo "00 - Setup"; `1` si ese grupo no corrió | Medicamento usado en `POST /disponibilidad` |
| `lat_usuario` / `lng_usuario` / `ciudad_usuario` | `4.6640` / `-74.0540` / `Bogota` | Coordenadas (Rosales, Bogotá — coinciden con los datos demo del seed) |
| **01 — Carga normal** | | |
| `baseline_users` | `20` | Usuarios virtuales |
| `baseline_rampup_s` | `60` | Rampa en segundos |
| `baseline_duration_s` | `300` (5 min) | Duración total |
| **02 — Pico (spike)** | | |
| `spike_floor_users` | `10` | Carga baja antes del pico |
| `spike_floor_startup_s` / `spike_floor_hold_s` / `spike_floor_shutdown_s` | `5` / `30` / `5` | Rampa/sostén/baja de la carga baja |
| `spike_peak_users` | `150` | Usuarios en el pico |
| `spike_peak_delay_s` | `30` | Segundos desde el inicio hasta que arranca el pico |
| `spike_peak_startup_s` / `spike_peak_hold_s` / `spike_peak_shutdown_s` | `5` / `60` / `15` | Salto súbito / sostén / bajada del pico |
| **03 — Estrés escalonado** | | |
| `stress_step1_users` … `stress_step4_users` | `25` / `50` / `100` / `200` | Usuarios de cada escalón |
| `stress_step1_delay_s` … `stress_step4_delay_s` | `0` / `180` / `360` / `540` | Cuándo arranca cada escalón (segundos desde el inicio) |
| `stress_step_duration_s` | `180` (3 min) | Duración de cada escalón |
| `stress_step_rampup_s` | `10` | Rampa dentro de cada escalón |
| **04 — Ráfaga de rate limiting** | | |
| `ratelimit_users` | `30` | Usuarios simultáneos golpeando `/auth/login` |
| `ratelimit_rampup_s` | `2` | Rampa (casi simultánea, a propósito) |
| `ratelimit_loops` | `3` | Iteraciones por usuario |
| **05 — Resiliencia Brevo/reCAPTCHA (HU-S3-10)** | | |
| `hu_s3_10_users` | `0` (**inerte por defecto**) | Ver sección 5, está bloqueado |

Si cambias `stress_step_duration_s`, recuerda ajustar también los `stress_stepN_delay_s` a mano
(no se recalculan solos, a propósito: así no hay aritmética anidada frágil dentro del `.jmx`).

## 4. Leer el reporte

Cada corrida deja dos cosas en `perf/results/` (no se versionan, ver `.gitignore`):

- `<escenario>.jtl` — datos crudos, uno por muestra.
- `<escenario>_html/index.html` — reporte HTML de JMeter (abrir en el navegador): gráficas de
  tiempo de respuesta, throughput, porcentaje de error, etc.

Para una lectura rápida en texto, sin abrir el HTML:

```bash
python3 perf/check_thresholds.py perf/results/baseline.jtl
python3 perf/check_thresholds.py perf/results/rate_limit.jtl --rate-limit-check
```

El primero imprime, por endpoint: cantidad de muestras, tiempo promedio, **p95**, throughput
(**req/s**) y tasa de error, y dice si cada uno cumple los umbrales (`--p95-ms` y
`--error-rate-pct`, ambos editables por línea de comandos). El segundo confirma específicamente
que la ráfaga de login produjo **al menos un 429** y **ningún 5xx**.

### Umbrales iniciales (por acordar con el equipo)

| Umbral | Valor por defecto | Nota |
|---|---|---|
| p95 máximo | 800 ms | Generoso para un prototipo académico con Postgres en Docker local; bájalo si el equipo quiere ser más estricto |
| Tasa de error máxima | 1% | Excluye los 429 esperados del escenario de ráfaga (ese se evalúa aparte, con `--rate-limit-check`) |

Estos dos números son un punto de partida, **no** un SLA acordado — decídanlos como equipo y
ajusten el `--p95-ms`/`--error-rate-pct` que le pasan a `check_thresholds.py` (o guárdenlo en un
script propio que los fije).

### ⚠️ El cuello de botella puede ser la máquina que genera la carga

JMeter en modo no-GUI (`-n`) ya evita lo peor (nada de interfaz gráfica ni "Ver árbol de
resultados"), pero a partir de unos cuantos cientos de hilos concurrentes **la propia máquina
que corre JMeter** puede quedarse sin CPU, sin memoria o sin sockets antes que el backend. Señales
de esto: el p95 sube pero el uso de CPU/red del backend no sube con él, o JMeter mismo empieza a
tirar `OutOfMemoryError` o `java.net.BindException` en su log (`jmeter.log`). Si ves eso,
el problema no es MediCerca: hay que generar la carga desde otra máquina, o repartirla entre
varias instancias de JMeter (modo distribuido `-R`), antes de sacar conclusiones sobre el
backend.

## 5. HU-S3-10 (resiliencia ante Brevo/reCAPTCHA) — **bloqueado, solo documentado**

### Hallazgos

- `email.py` y `captcha.py` llaman a Brevo y a Google reCAPTCHA con una **URL hardcodeada**
  (`BREVO_API_URL`, `GOOGLE_SITEVERIFY_URL`), no leída de `settings`. Sin eso, no hay forma de
  redirigir esas llamadas a un stub local en un entorno de pruebas sin tocar la red real.
- `enviar_correo()` (Brevo) **ya es resiliente**: atrapa `httpx.HTTPError` (incluye timeouts) y
  nunca propaga el fallo, así que un Brevo caído o lento no tumba el registro ni la aprobación
  de una orden. El riesgo que sí queda: la llamada es **síncrona y bloqueante** (timeout de 10 s)
  dentro del propio request — un Brevo lento bajo una ráfaga de registros puede agotar el pool
  de workers del backend. Es un hallazgo de **rendimiento**, no de corrección.
- `verificar_captcha()` (reCAPTCHA), en cambio, **si propaga el fallo**: si hay
  `RECAPTCHA_SECRET_KEY` configurada y Google responde lento o con error, el usuario recibe un
  422 — ahí no hay tolerancia a fallas todavía.

### Cambio propuesto (NO aplicado — a pedido explícito del usuario, solo queda documentado)

```python
# app/config.py — Settings
recaptcha_verify_url: str = "https://www.google.com/recaptcha/api/siteverify"
brevo_api_url: str = "https://api.brevo.com/v3/smtp/email"
```

y usar `settings.recaptcha_verify_url` / `settings.brevo_api_url` en vez de las constantes
hardcodeadas en `captcha.py`/`email.py`. Mismo valor por defecto, cero cambio de comportamiento
salvo que se sobreescriba por variable de entorno — exactamente el tipo de bandera que se pidió.

### Qué queda listo para cuando se aplique

- `perf/stubs/mock_brevo_recaptcha.py`: servidor local (sin dependencias nuevas) que simula
  Brevo/reCAPTCHA en modo `ok`, `slow`, `timeout`, `error` o `down`. Pruébalo solo:

  ```bash
  python3 perf/stubs/mock_brevo_recaptcha.py --port 9999 --mode timeout --delay-seconds 8
  ```

- En `medicerca_load.jmx`, el Thread Group **"05 - BLOQUEADO - Resiliencia Brevo-reCAPTCHA"**
  existe como plantilla, con `hu_s3_10_users=0` por defecto (0 hilos = no genera tráfico). El día
  que se aplique el cambio de arriba:
  1. Arranca el backend con `RECAPTCHA_SECRET_KEY=cualquier-valor-no-vacio` (para que
     `verificar_captcha` deje de omitirse) y con `RECAPTCHA_VERIFY_URL`/`BREVO_API_URL` apuntando
     al stub (`http://localhost:9999/...`).
  2. Levanta el stub en el modo que quieras probar (`slow`, `timeout`, `error`).
  3. Corre `perf/run.sh baseline -Jhu_s3_10_users=20 -Jbaseline_users=0 ...` (o agrega un
     `run.sh` con un caso `resiliencia` nuevo) y confirma en el `.jtl` que el registro sigue
     devolviendo 201 pese a la falla externa.
  - Sin ese cambio, el escenario 05 solo puede probarse manualmente con `curl` apuntando el
    stub directamente a las rutas de Brevo/reCAPTCHA vía `/etc/hosts` o un proxy — no es algo que
    JMeter pueda activar por sí solo contra el código actual.

## 6. Qué se validó al construir este plan

Sin poder instalar JMeter en este entorno, se validó todo lo que sí era posible sin él:

- El `.jmx` se generó por código y se comprobó como **XML bien formado** (8 Thread Groups
  nativos + 1 Ultimate Thread Group + 22 HTTP Samplers + 22 Response Assertions, conteos
  verificados).
- El backend se levantó localmente con **SQLite** (mismo mecanismo que usa la suite de pytest
  del proyecto, sin Docker ni Postgres) y se probó con `curl`, exactamente con los mismos
  cuerpos JSON que usa el `.jmx`:
  - `POST /auth/register` + `POST /auth/verificar-registro` (vía
    `crear_usuarios_prueba.py`) — los 3 usuarios de prueba quedaron creados y verificados.
  - `POST /auth/login` → devuelve `access_token`.
  - `GET /medicamentos?q=acetaminofen&limit=1` → `items[0].id` (así resuelve `medicamento_id`
    el grupo "00 - Setup").
  - `POST /disponibilidad` con ese `medicamento_id` y las coordenadas de Rosales → 200, con el
    punto de venta más cercano correctamente identificado.
  - Ráfaga de 25 logins seguidos contra `/auth/login`: las primeras ~19 respondieron 200, el
    resto 429, **ninguna 5xx** — confirma en vivo el comportamiento que el escenario 04 y
    `check_thresholds.py --rate-limit-check` esperan.
- `check_thresholds.py` se probó con archivos `.jtl` sintéticos (formato de columnas real de
  JMeter) en ambos modos (umbrales y `--rate-limit-check`), incluyendo un caso que debe fallar.
- `run.sh` se probó con un `jmeter` falso en el `PATH` para confirmar que arma la línea de
  comandos correcta y apaga los grupos que no tocan en cada escenario.

Lo único que **no** se pudo hacer fue correr `jmeter -n` de verdad — eso queda para que lo
corras tú (o para una próxima sesión con acceso a la descarga de JMeter), siguiendo el
"Cómo verificar tu trabajo" que pidió el encargo original.
