# MediCerca — Escenarios de calidad: cómo demostrarlos

Los 6 escenarios están implementados en el proyecto y tienen evidencia automatizada en
`backend/tests/test_escenarios_calidad.py` (20 tests). Estado de la suite completa: **96 tests pasan**.

```bash
cd backend
pytest tests/test_escenarios_calidad.py -v     # solo los escenarios (≈15 s)
pytest -q                                      # toda la suite (≈75 s)
```

| # | Escenario | Qué se muestra | Evidencia |
|---|-----------|----------------|-----------|
| 1 | Seguridad | Bloqueo, OTP, token revocado, acceso cruzado | `test_seg_*` |
| 2 | Modificabilidad | IPS nueva solo con configuración | `test_mod_*` |
| 3 | Disponibilidad | Cae una IPS y el sistema sigue | `test_disp_*` |
| 4 | Usabilidad 1 | Cancelar un domicilio pedido por error | `test_usab1_*` + frontend |
| 5 | Usabilidad 2 | Punto de venta más cercano | `test_usab2_*` + frontend |
| 6 | Usabilidad 3 | Retroalimentación de cada acción | `test_usab3_*` + frontend |

## Cambios al texto de tres escenarios (para el documento)

Se ajustaron para que coincidan con lo que el sistema realmente hace y se puede demostrar.

**Usability 1: Cancel a delivery requested by mistake** (reemplaza a "Reschedule delivery").
- *Source:* Patient affiliated to an EPS. *Stimulus:* The patient realizes a delivery was requested by mistake or is no longer needed.
- *Artifact:* Delivery detail screen and cancel endpoint. *Environment:* Normal operation; patient logged in; delivery in "confirmed" or "in preparation" state.
- *Response:* The system shows a visible "Cancel delivery" button only while cancelling is still possible, asks for confirmation, cancels it, shows a green confirmation with date and time, records it in the delivery timeline and frees the medical order so it can be requested again. Once the delivery is on its way, the system rejects the cancellation with a clear message.
- *Response measure:* The patient cancels in 3 clicks or less from the deliveries list and in under 30 seconds without help; 100% of cancellations before dispatch succeed and 100% after dispatch are rejected with a clear message.

**Usability 2** — se quitan "opening hours" y "simple map": el punto trae *address, distance and a "how to get there" map link*.

**Usability 3** — la confirmación es *en pantalla (verde/rojo) y por correo*; el SMS queda fuera de alcance.

## 1. Seguridad

*Demo en vivo (Swagger, `http://localhost:8000/docs`):*
1. `POST /auth/login` con una contraseña mala 5 veces → 401 cada vez.
2. Sexto intento, incluso con la contraseña correcta → **429**.
3. `POST /auth/logout` y luego `GET /auth/me` con el mismo token → **401**.
4. Con el token de otro paciente, `GET /domicilios/{ips}/{id}` → **403**.

*Cambio de código:* se corrigió un fallo real. Al vencer el bloqueo de 15 min el contador seguía en 5 y un solo error más bloqueaba de nuevo.
*Tests clave:* `test_seg_el_bloqueo_vence_y_el_contador_empieza_de_cero` (fallaba con el código anterior: contador = 6) y `test_seg_acceso_cruzado_entre_pacientes_se_niega_al_100_por_ciento`.

## 2. Modificabilidad — agregar una IPS

Solo configuración, **0 archivos de código**:
1. `infra/docker-compose.yml`: descomentar el servicio `db_ips4`.
2. `backend/.env`: descomentar `DATABASE_URL_IPS_4=...`.
3. `docker compose up -d` y registrar la IPS:
```bash
curl -X POST http://localhost:8000/api/v1/admin/ips \
  -H "X-Admin-Key: <ADMIN_KEY>" -H "Content-Type: application/json" \
  -d '{"codigo":"IPS-NORTE","nombre_ficticio":"IPS Norte Integrada","clave_conexion":"demo_ips_4"}'
```
Desde ese momento aparece en `GET /ips`, en `GET /health` y en la disponibilidad, y sus pacientes usan órdenes y domicilios sin cambios.

*Cambio de código (una sola vez):* `ips_connection_registry` ahora lee cualquier `DATABASE_URL_IPS_<N>` del entorno (antes estaba escrito a mano para 3 IPS) y se agregó `POST /admin/ips`.
*Test clave:* `test_mod_una_ips_nueva_funciona_solo_con_configuracion_sin_tocar_codigo`.
*Medida del tiempo (< 4 h):* cronometra estos 3 pasos en la demo.

## 3. Disponibilidad — falla de una IPS

*Demo en vivo:*
```bash
docker compose stop db_ips2
curl http://localhost:8000/api/v1/health          # 503 y "demo_ips_2": false
# POST /disponibilidad → 200 con resultados de IPS 1 y 3 + "aviso" de la IPS 2
docker compose start db_ips2                       # se recupera sola
```
Un paciente de la IPS 1 sigue cargando órdenes y viendo sus domicilios durante la caída.

*Cambios de código:* la consulta ya no revienta si una IPS falla (resultados parciales + `aviso` + `ips_no_disponibles`), timeout de conexión de 3 s (`IPS_CONNECT_TIMEOUT_SEGUNDOS`) y el arranque tolera una IPS caída.
*Ojo:* mientras una IPS esté caída, el `HEALTHCHECK` de Docker marcará el backend como *unhealthy* (porque `/health` responde 503 a propósito); el servicio sigue atendiendo.
*Tests clave:* `test_disp_health_responde_503_e_identifica_la_ips_caida`, `test_disp_la_consulta_devuelve_resultados_parciales_con_aviso`, `test_disp_los_pacientes_de_otra_ips_siguen_operando_durante_la_falla`.

## 4–6. Usabilidad

Las medidas con personas (tiempo, clics, % de usuarios) se demuestran con una prueba corta:
5 personas, un cronómetro y la tarea escrita en una hoja ("cancela este domicilio", "encuentra la sede más cercana").
Anota tiempo, clics y si necesitó ayuda. La parte automatizable ya está en los tests.

- **Usabilidad 1:** `Mis domicilios` → abrir un domicilio → **Cancelar domicilio** → confirmar → aviso verde. Después de "En camino" el botón desaparece y el backend rechaza con mensaje claro.
- **Usabilidad 2:** Catálogo → un medicamento → **Usar mi ubicación** (o escribir latitud/longitud) → **Buscar disponibilidad**. El punto más cercano sale resaltado, con dirección, distancia y **Cómo llegar**. Para probar sin GPS: Chapinero `4.6490`, `-74.0602`.
- **Usabilidad 3:** al crear/cancelar un domicilio, cargar una orden o aprobarla/rechazarla aparece un aviso verde (o rojo si falla) con qué pasó, fecha, hora y lugar. Además se envía correo (requiere `EMAIL_MODO=real` y `BREVO_API_KEY`; en modo simulado no sale nada).
