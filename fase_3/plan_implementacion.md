# Plan de Implementación — Fase 3
## Ingestión y Almacenamiento de Datos IoT en Base de Datos de Series Temporales

**Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026**
**Profesor:** Gonzalo Llano R.

---

## Índice

1. [Contexto y punto de partida](#1-contexto-y-punto-de-partida)
2. [Arquitectura de la fase](#2-arquitectura-de-la-fase)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Estructura de archivos a crear](#4-estructura-de-archivos-a-crear)
5. [Paso 1 — docker-compose.yml](#5-paso-1--docker-composeyml)
6. [Paso 2 — mosquitto.conf](#6-paso-2--mosquittoconf)
7. [Paso 3 — gateway/requirements.txt](#7-paso-3--gatewayrequirementstxt)
8. [Paso 4 — gateway/Dockerfile](#8-paso-4--gatewaydockerfile)
9. [Paso 5 — gateway/gateway.py](#9-paso-5--gatewaygatewaypy)
10. [Paso 6 — Levantar todos los servicios](#10-paso-6--levantar-todos-los-servicios)
11. [Paso 7 — Verificar InfluxDB](#11-paso-7--verificar-influxdb)
12. [Paso 8 — Verificar el gateway Python](#12-paso-8--verificar-el-gateway-python)
13. [Paso 9 — Verificar datos almacenados](#13-paso-9--verificar-datos-almacenados)
14. [Queries Flux de referencia](#14-queries-flux-de-referencia)
15. [Troubleshooting](#15-troubleshooting)
16. [Entregables para el profesor](#16-entregables-para-el-profesor)
17. [Conexión con Fase 4](#17-conexión-con-fase-4)

---

## 1. Contexto y punto de partida

### Qué existe ya (Fase 2)

La carpeta `fase_2/` contiene un simulador funcional con los siguientes servicios:

| Servicio | Imagen | Puerto | Estado |
|---|---|---|---|
| `mqtt_broker` | `eclipse-mosquitto:latest` | `1883` | ✅ Operativo |
| `iot_simulator` | imagen local (Python) | — | ✅ Operativo |

El simulador publica mensajes JSON cada 15/30/60 segundos en los siguientes topics MQTT:
- `agricultura/sensores/parcela_1` — Caña de azúcar, 5 ha
- `agricultura/sensores/parcela_2` — Caña de azúcar, 3.5 ha
- `agricultura/sensores/parcela_3` — Palma de aceite, 8 ha
- `agricultura/sensores/parcela_4` — Palma de aceite, 6.5 ha

**Fuentes de datos del simulador:**
- Parcelas 1 y 2 (caña): `sugarcane-prediction-dataset.csv` — datos reales de campo
- Parcelas 3 y 4 (palma): `crop-production-countries.csv` (temperatura + lluvia reales) + proceso AR(1) para el resto

**Payload de ejemplo que llega al broker:**
```json
{
  "timestamp": "2026-05-03 14:30:00",
  "parcela": "parcela_1",
  "cultivo": "sugarcane",
  "area_ha": 5.0,
  "temperature_air": 28.47,
  "humidity": 70.83,
  "rainfall": 1462.5,
  "soil_ph": 7.21,
  "soil_moisture": 26.8,
  "solar_radiation": 22.34
}
```

> **Importante:** no todos los campos de sensor aparecen en cada mensaje.
> La frecuencia por sensor es 15 s / 30 s / 60 s, y el payload solo incluye
> los sensores que dispararon en ese tick. El gateway debe manejar payloads parciales.

### Qué falta construir (Fase 3)

```
[YA EXISTE]                         [FASE 3 — CONSTRUIR]
Sensores IoT (Python simulator)
        │
        ▼
Broker MQTT (Mosquitto) ──────────► Gateway IoT (Python) ──────────► InfluxDB
                                           │
                                    suscribe a MQTT
                                    parsea JSON
                                    valida campos
                                    construye Point
                                    escribe en bucket
```

---

## 2. Arquitectura de la fase

### Flujo completo de datos

```
simulator.py (fase_2)
    │ publica JSON cada 15-60 s por parcela
    ▼
eclipse-mosquitto :1883
    │ topic: agricultura/sensores/#
    ▼
gateway.py (Python — paho-mqtt + influxdb-client)
    │ on_message():
    │   1. json.loads(payload)
    │   2. validar campos obligatorios
    │   3. construir influxdb_client.Point
    │   4. write_api.write(bucket, record=point)
    ▼
InfluxDB :8086
    │ org: agricultura | bucket: agro_iot_data
    │ measurement: sensor_data
    ▼
Data Explorer (UI web InfluxDB) — Flux queries
    ▼
[Fase 4] Procesamiento, alertas y analítica
```

### Modelo de datos en InfluxDB

InfluxDB v2 usa el concepto de **measurement + tags + fields + timestamp**:

| Componente | Valor | Descripción |
|---|---|---|
| **measurement** | `sensor_data` | Nombre de la "tabla" |
| **tag: parcela** | `parcela_1` … `parcela_4` | Indexado — para filtrar por parcela |
| **tag: cultivo** | `sugarcane` / `oil_palm` | Indexado — para filtrar por cultivo |
| **tag: area_ha** | `"5.0"` | Indexado — área de la parcela |
| **field: temperature_air** | `28.47` | Float — valor del sensor |
| **field: humidity** | `70.83` | Float |
| **field: rainfall** | `1462.5` | Float |
| **field: soil_ph** | `7.21` | Float |
| **field: soil_moisture** | `26.8` | Float |
| **field: solar_radiation** | `22.34` | Float |
| **field: wind_speed** | `8.61` | Float |
| **field: evapotranspiration** | `5.01` | Float |
| **timestamp** | nanoseconds epoch | Convertido desde `payload.timestamp` |

> **Regla crítica de InfluxDB:** los `tags` son strings indexados (usados en
> filtros WHERE). Los `fields` son valores numéricos almacenados como serie temporal.
> Nunca poner un valor numérico de sensor como tag — degradaría el rendimiento.

---

## 3. Stack tecnológico

| Tecnología | Versión | Rol | Puerto |
|---|---|---|---|
| Eclipse Mosquitto | `latest` | Broker MQTT | `1883` |
| Python 3.11 + paho-mqtt | `paho-mqtt==1.6.1` | Suscripción a topics MQTT en el gateway | — |
| Python 3.11 + influxdb-client | `influxdb-client==1.40.0` | Escritura en InfluxDB v2 desde el gateway | — |
| InfluxDB | `2.7` | Base de datos de series temporales (raw data) | `8086` |
| Python simulator | imagen local (Fase 2) | Fuente de datos IoT simulados | — |

### Credenciales fijas para el lab

> Hardcodeadas para el entorno de laboratorio. **No usar en producción.**

| Parámetro | Valor |
|---|---|
| InfluxDB organización | `agricultura` |
| InfluxDB bucket | `agro_iot_data` |
| InfluxDB usuario admin | `admin` |
| InfluxDB contraseña admin | `agro_admin_2026` |
| InfluxDB API token | `agro-iot-token-fase3-icesi-2026` |
| InfluxDB URL | `http://localhost:8086` |

---

## 4. Estructura de archivos a crear

El agente debe crear exactamente esta estructura dentro de `fase_3/`:

```
proyecto_final/
├── datasets/                        ← ya existe
├── fase_2/                          ← ya existe, NO modificar
└── fase_3/
    ├── plan_implementacion.md       ← este archivo
    ├── docker-compose.yml           ← 4 servicios: mosquitto + simulator + gateway + influxdb
    ├── mosquitto/
    │   └── mosquitto.conf           ← idéntico al de fase_2
    └── gateway/
        ├── Dockerfile               ← python:3.11-slim + dependencias
        ├── requirements.txt         ← paho-mqtt + influxdb-client
        └── gateway.py               ← Gateway IoT: suscribe MQTT → escribe InfluxDB
```

> `fase_3/` debe ser completamente autocontenida.
> `docker compose up --build` desde dentro de `fase_3/` levanta todo el sistema.

---

## 5. Paso 1 — docker-compose.yml

Crear `fase_3/docker-compose.yml` con el siguiente contenido exacto:

```yaml
version: "3.8"

# ─────────────────────────────────────────────────────────────────────────────
# Fase 3 — Ingestión IoT en InfluxDB via Gateway Python
# Servicios: Mosquitto + Simulador + Gateway Python + InfluxDB
# ─────────────────────────────────────────────────────────────────────────────

services:

  # ── 1. Broker MQTT ─────────────────────────────────────────────────────────
  mosquitto:
    image: eclipse-mosquitto:latest
    container_name: mqtt_broker
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "mosquitto_sub -t '$$SYS/#' -C 1 -i healthcheck -W 3"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── 2. Simulador de sensores IoT ───────────────────────────────────────────
  simulator:
    build:
      context: ../fase_2
      dockerfile: Dockerfile
    container_name: iot_simulator
    depends_on:
      mosquitto:
        condition: service_healthy
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - SUGARCANE_PATH=/app/datasets/sugarcane-prediction-dataset.csv
      - PALM_PATH=/app/datasets/crop-production-countries.csv
    volumes:
      - ../datasets:/app/datasets:ro
    restart: unless-stopped

  # ── 3. Base de datos de series temporales ──────────────────────────────────
  influxdb:
    image: influxdb:2.7
    container_name: influxdb_agro
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_ORG=agricultura
      - DOCKER_INFLUXDB_INIT_BUCKET=agro_iot_data
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=agro_admin_2026
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=agro-iot-token-fase3-icesi-2026
      - DOCKER_INFLUXDB_INIT_RETENTION=0
    volumes:
      - influxdb_data:/var/lib/influxdb2
      - influxdb_config:/etc/influxdb2
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "influx", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  # ── 4. Gateway IoT — Python ─────────────────────────────────────────────────
  gateway:
    build:
      context: ./gateway
      dockerfile: Dockerfile
    container_name: iot_gateway
    depends_on:
      mosquitto:
        condition: service_healthy
      influxdb:
        condition: service_healthy
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - MQTT_TOPIC=agricultura/sensores/#
      - INFLUX_URL=http://influxdb:8086
      - INFLUX_TOKEN=agro-iot-token-fase3-icesi-2026
      - INFLUX_ORG=agricultura
      - INFLUX_BUCKET=agro_iot_data
    restart: unless-stopped

volumes:
  mosquitto_data:
  mosquitto_log:
  influxdb_data:
  influxdb_config:
```

### Orden de arranque garantizado por healthchecks

```
1. mosquitto  → arranca primero
2. influxdb   → arranca; DOCKER_INFLUXDB_INIT_MODE=setup crea org + bucket + token automáticamente
3. simulator  → espera mosquitto healthy; empieza a publicar en MQTT
4. gateway    → espera mosquitto + influxdb healthy; suscribe y empieza a escribir en InfluxDB
```

> **Nota:** `DOCKER_INFLUXDB_INIT_MODE=setup` solo se ejecuta si el volumen
> `influxdb_data` está vacío (primer arranque). En reinicios posteriores se ignora.

---

## 6. Paso 2 — mosquitto.conf

Crear `fase_3/mosquitto/mosquitto.conf` con el siguiente contenido:

```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_type all
```

---

## 7. Paso 3 — gateway/requirements.txt

Crear `fase_3/gateway/requirements.txt` con el siguiente contenido:

```
paho-mqtt==1.6.1
influxdb-client==1.40.0
```

---

## 8. Paso 4 — gateway/Dockerfile

Crear `fase_3/gateway/Dockerfile` con el siguiente contenido:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway.py .

CMD ["python", "gateway.py"]
```

---

## 9. Paso 5 — gateway/gateway.py

Este es el archivo más importante. Implementa el Gateway IoT en Python puro.

Crear `fase_3/gateway/gateway.py` con el siguiente contenido **exacto**:

```python
#!/usr/bin/env python3
"""
Fase 3 — Gateway IoT Agrícola
Universidad ICESI — Sistemas y Comunicaciones I — Mayo 2026

Rol: Edge Computing Gateway
  - Suscribe al Broker MQTT (Mosquitto)
  - Recibe mensajes JSON de los 4 sensores simulados
  - Valida y transforma cada mensaje
  - Escribe en InfluxDB como serie temporal

Pipeline:
  Broker MQTT → on_message() → validar → Point InfluxDB → write_api.write()
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gateway")

# ─── Configuración desde variables de entorno ─────────────────────────────────
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC  = os.environ.get("MQTT_TOPIC", "agricultura/sensores/#")

INFLUX_URL    = os.environ.get("INFLUX_URL",    "http://localhost:8086")
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "agro-iot-token-fase3-icesi-2026")
INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "agricultura")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "agro_iot_data")

# ─── Campos de sensores válidos ───────────────────────────────────────────────
# Solo estos campos se almacenan como fields en InfluxDB.
# Todos los demás keys del payload se ignoran.
SENSOR_FIELDS = {
    "temperature_air",
    "humidity",
    "rainfall",
    "soil_ph",
    "soil_moisture",
    "solar_radiation",
    "wind_speed",
    "evapotranspiration",
}

# ─── Cliente InfluxDB ─────────────────────────────────────────────────────────
influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def parse_timestamp(ts_str: str) -> datetime:
    """
    Convierte el timestamp del payload "YYYY-MM-DD HH:MM:SS" a datetime UTC.
    Si falla el parseo, usa el timestamp actual como fallback.
    """
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        log.warning("Timestamp inválido '%s' — usando tiempo actual", ts_str)
        return datetime.now(tz=timezone.utc)


def build_point(payload: dict) -> Point | None:
    """
    Construye un influxdb_client.Point desde el payload JSON del sensor.

    Retorna None si el payload no tiene los campos obligatorios o
    si no contiene ningún field de sensor válido.

    Estructura del Point resultante:
      measurement: sensor_data
      tags:        parcela, cultivo, area_ha
      fields:      los sensores presentes en este tick (payload parcial OK)
      timestamp:   derivado de payload["timestamp"]
    """
    # Validar campos obligatorios
    for required in ("parcela", "cultivo", "timestamp"):
        if not payload.get(required):
            log.warning("Campo obligatorio '%s' faltante: %s", required, payload)
            return None

    # Extraer solo los fields de sensores presentes en este payload
    fields = {}
    for sensor in SENSOR_FIELDS:
        value = payload.get(sensor)
        if value is not None:
            try:
                fields[sensor] = float(value)
            except (ValueError, TypeError):
                log.warning("Valor no numérico en '%s': %s", sensor, value)

    if not fields:
        log.warning("Payload sin campos de sensor válidos: %s", payload)
        return None

    # Construir el Point
    ts = parse_timestamp(payload["timestamp"])

    point = (
        Point("sensor_data")
        .tag("parcela", payload["parcela"])
        .tag("cultivo", payload["cultivo"])
        .tag("area_ha", str(payload.get("area_ha", "")))
        .time(ts, WritePrecision.NANOSECONDS)
    )

    for field_name, field_value in fields.items():
        point = point.field(field_name, field_value)

    return point


def on_connect(client, userdata, flags, rc):
    """Callback al conectar al broker MQTT."""
    if rc == 0:
        log.info("✔ Conectado al broker MQTT %s:%d", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPIC, qos=1)
        log.info("Suscrito a topic: %s", MQTT_TOPIC)
    else:
        log.error("✘ Error de conexión MQTT rc=%d", rc)


def on_disconnect(client, userdata, rc):
    """Callback al desconectarse del broker."""
    if rc != 0:
        log.warning("Desconexión inesperada del broker MQTT (rc=%d) — reconectando…", rc)


def on_message(client, userdata, msg):
    """
    Callback principal: se ejecuta por cada mensaje MQTT recibido.

    Flujo:
      1. Decodificar bytes → string UTF-8
      2. Parsear JSON → dict
      3. Construir Point de InfluxDB
      4. Escribir en bucket
    """
    try:
        # 1. Decodificar
        raw = msg.payload.decode("utf-8")

        # 2. Parsear JSON
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error("JSON inválido en topic '%s': %s | raw: %s", msg.topic, e, raw[:200])
            return

        # 3. Construir Point
        point = build_point(payload)
        if point is None:
            return

        # 4. Escribir en InfluxDB
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # Log resumido para no saturar la consola
        fields_presentes = [f for f in SENSOR_FIELDS if f in payload]
        log.info(
            "[%s] %s → InfluxDB | campos=%s",
            payload.get("parcela", "?"),
            payload.get("cultivo", "?"),
            fields_presentes,
        )

    except Exception as e:
        log.error("Error procesando mensaje de '%s': %s", msg.topic, e, exc_info=True)


def connect_with_retry(client: mqtt.Client, max_retries: int = 15) -> bool:
    """Intenta conectar al broker MQTT con reintentos."""
    for attempt in range(1, max_retries + 1):
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            return True
        except Exception as exc:
            log.warning("Intento %d/%d — broker no disponible: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(3)
    return False


def main():
    log.info("=" * 60)
    log.info("  Gateway IoT Agrícola — Fase 3")
    log.info("  Universidad ICESI — Sistemas y Comunicaciones I")
    log.info("=" * 60)
    log.info("MQTT  : %s:%d → topic %s", MQTT_BROKER, MQTT_PORT, MQTT_TOPIC)
    log.info("InfluxDB: %s | org=%s | bucket=%s", INFLUX_URL, INFLUX_ORG, INFLUX_BUCKET)

    # Configurar cliente MQTT
    client = mqtt.Client(client_id="iot_gateway_agro", protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    # Conectar al broker con reintentos
    if not connect_with_retry(client):
        log.error("No se pudo conectar al broker MQTT después de varios intentos. Abortando.")
        return

    log.info("Gateway iniciado — escuchando mensajes MQTT…")

    try:
        # loop_forever() bloquea e invoca los callbacks automáticamente
        # También maneja reconexiones automáticas si el broker se cae
        client.loop_forever()
    except KeyboardInterrupt:
        log.info("Señal de interrupción — deteniendo gateway…")
    finally:
        client.disconnect()
        write_api.close()
        influx_client.close()
        log.info("Gateway detenido correctamente.")


if __name__ == "__main__":
    main()
```

### Explicación del flujo en `on_message()`

```
msg.payload (bytes)
      │ .decode("utf-8")
      ▼
string JSON
      │ json.loads()
      ▼
dict Python { timestamp, parcela, cultivo, area_ha, temperature_air, ... }
      │ build_point()
      │   ├── validar: parcela, cultivo, timestamp presentes
      │   ├── extraer solo SENSOR_FIELDS → dict fields{}
      │   │   (el payload puede ser parcial — no todos los sensores
      │   │    están en cada tick, depende de la frecuencia)
      │   ├── parse_timestamp() → datetime UTC
      │   └── construir Point("sensor_data")
      │         .tag("parcela", ...)
      │         .tag("cultivo", ...)
      │         .tag("area_ha", ...)
      │         .field("temperature_air", 28.47)
      │         .field("humidity", 70.83)
      │         ...
      │         .time(ts, WritePrecision.NANOSECONDS)
      ▼
write_api.write(bucket="agro_iot_data", record=point)
      ▼
InfluxDB — measurement: sensor_data
```

### Por qué `SYNCHRONOUS` en write_api

`write_options=SYNCHRONOUS` hace que cada `write()` espere confirmación de InfluxDB
antes de continuar. Esto garantiza que no se pierdan puntos si InfluxDB está lento.
La alternativa `ASYNCHRONOUS` es más rápida pero puede perder puntos en reinicio.
Para un laboratorio con 4 parcelas enviando cada 15 s, el modo síncrono es suficiente.

---

## 10. Paso 6 — Levantar todos los servicios

```bash
# Desde la carpeta fase_3/
cd fase_3

# Primera vez: construir imágenes y levantar
docker compose up --build

# En background (recomendado para demostración)
docker compose up --build -d

# Ver logs en tiempo real de un servicio específico
docker compose logs -f gateway
docker compose logs -f influxdb
```

### Salida esperada en logs al arrancar correctamente

```
influxdb_agro  | ts=... msg="Welcome to InfluxDB"
influxdb_agro  | ts=... msg="Listening" service=tcp-listener addr=:8086
iot_gateway    | ========================================================
iot_gateway    | Gateway IoT Agrícola — Fase 3
iot_gateway    | ========================================================
iot_gateway    | MQTT  : mosquitto:1883 → topic agricultura/sensores/#
iot_gateway    | InfluxDB: http://influxdb:8086 | org=agricultura | bucket=agro_iot_data
iot_gateway    | ✔ Conectado al broker MQTT mosquitto:1883
iot_gateway    | Suscrito a topic: agricultura/sensores/#
iot_gateway    | Gateway iniciado — escuchando mensajes MQTT…
iot_gateway    | [parcela_1] sugarcane → InfluxDB | campos=['temperature_air', 'humidity', 'soil_ph', ...]
iot_gateway    | [parcela_3] oil_palm  → InfluxDB | campos=['temperature_air', 'humidity', ...]
```

---

## 11. Paso 7 — Verificar InfluxDB

### Verificar que InfluxDB está corriendo y respondiendo

```bash
# Ping desde el host
curl -s -o /dev/null -w "%{http_code}" http://localhost:8086/ping
# Respuesta esperada: 204

# Ping desde dentro del contenedor
docker exec influxdb_agro influx ping
# Respuesta esperada: OK
```

### Verificar que el bucket fue creado

```bash
docker exec influxdb_agro influx bucket list \
  --token agro-iot-token-fase3-icesi-2026 \
  --org agricultura
# Debe mostrar: agro_iot_data | infinite retention
```

### Acceder a la UI web

1. Abrir `http://localhost:8086`
2. Usuario: `admin` | Contraseña: `agro_admin_2026`
3. Ir a **Data → Buckets** → verificar que existe `agro_iot_data`

---

## 12. Paso 8 — Verificar el gateway Python

### Ver que el gateway está recibiendo y escribiendo mensajes

```bash
docker compose logs -f gateway
```

Cada 15 segundos deben aparecer líneas como:
```
[parcela_1] sugarcane → InfluxDB | campos=['temperature_air', 'humidity']
[parcela_2] sugarcane → InfluxDB | campos=['temperature_air', 'humidity', 'wind_speed']
[parcela_3] oil_palm  → InfluxDB | campos=['temperature_air', 'humidity']
[parcela_4] oil_palm  → InfluxDB | campos=['temperature_air', 'humidity']
```

Cada 30 segundos también deben aparecer `soil_moisture`, `solar_radiation`.
Cada 60 segundos también deben aparecer `rainfall`, `soil_ph`, `evapotranspiration`.

### Verificar que el gateway suscribe al broker correctamente

```bash
# En otra terminal: suscribirse al mismo topic que el gateway
docker exec -it mqtt_broker mosquitto_sub -t "agricultura/sensores/#" -v
# Deben aparecer los JSON en tiempo real — si aparecen aquí, el gateway los recibe también
```

---

## 13. Paso 9 — Verificar datos almacenados

### Opción A — Data Explorer (UI web de InfluxDB)

1. Ir a `http://localhost:8086` → **Explore**
2. Seleccionar: bucket `agro_iot_data`, measurement `sensor_data`, field `temperature_air`
3. Hacer clic en **Submit** — deben aparecer 4 series (una por parcela)

### Opción B — Flux query en la UI

En **Explore → Script Editor** ejecutar:

```flux
from(bucket: "agro_iot_data")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```

### Opción C — influx CLI dentro del contenedor

```bash
docker exec influxdb_agro influx query \
  --token agro-iot-token-fase3-icesi-2026 \
  --org agricultura \
  'from(bucket: "agro_iot_data")
     |> range(start: -10m)
     |> filter(fn: (r) => r._measurement == "sensor_data")
     |> limit(n: 10)'
```

**Resultado esperado:** tabla con columnas `_time`, `_field`, `_value`, `parcela`, `cultivo`.

---

## 14. Queries Flux de referencia

### Query 1 — Última lectura de temperatura por parcela

```flux
from(bucket: "agro_iot_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "temperature_air")
  |> group(columns: ["parcela"])
  |> last()
```

### Query 2 — Temperatura promedio por cultivo (última hora)

```flux
from(bucket: "agro_iot_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "temperature_air")
  |> group(columns: ["cultivo"])
  |> mean()
```

### Query 3 — Comparar humedad de suelo caña vs palma

```flux
// Demuestra que los datos de ambos cultivos son distintos:
// Caña: soil_moisture 10–40% | Palma: soil_moisture 30–55%
from(bucket: "agro_iot_data")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "soil_moisture")
  |> group(columns: ["cultivo", "parcela"])
  |> mean()
  |> sort(columns: ["cultivo"])
```

### Query 4 — Contar registros almacenados por parcela

```flux
from(bucket: "agro_iot_data")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "temperature_air")
  |> group(columns: ["parcela"])
  |> count()
```

### Query 5 — Lecturas fuera de rango óptimo (pre-alerta para Fase 4)

```flux
// Caña: óptimo 28–35°C | Palma: óptimo 24–32°C
from(bucket: "agro_iot_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "temperature_air")
  |> filter(fn: (r) =>
      (r.cultivo == "sugarcane" and (r._value < 28.0 or r._value > 35.0)) or
      (r.cultivo == "oil_palm"  and (r._value < 24.0 or r._value > 32.0))
  )
```

---

## 15. Troubleshooting

### El gateway no conecta a Mosquitto

**Síntoma:** logs muestran "broker no disponible" en loop.

**Causa:** el broker no está healthy todavía. El gateway reintenta cada 3 s durante 15 intentos.

**Verificar:**
```bash
docker ps | grep mqtt_broker
docker compose logs mosquitto
```

Si el broker está corriendo pero el gateway no conecta:
```bash
docker compose restart gateway
```

---

### El gateway conecta pero no escribe en InfluxDB

**Síntoma:** logs muestran los mensajes recibidos pero no aparecen datos en InfluxDB.

**Causa más común:** token incorrecto o InfluxDB no terminó de inicializarse.

**Verificar:**
```bash
# Probar el token directamente
curl -s \
  -H "Authorization: Token agro-iot-token-fase3-icesi-2026" \
  "http://localhost:8086/api/v2/buckets?org=agricultura"
# Debe retornar JSON con el bucket agro_iot_data
```

**Si el volumen ya estaba inicializado con otro token:**
```bash
docker compose down -v   # elimina todos los volúmenes
docker compose up --build
```

---

### InfluxDB falla al arrancar con "already initialized"

**Síntoma:** el contenedor `influxdb_agro` sale con error sobre inicialización previa.

**Causa:** el volumen `influxdb_data` tiene datos de una ejecución anterior.

**Solución:** este error es inofensivo en la mayoría de los casos — InfluxDB sigue
funcionando. Si se quiere empezar de cero: `docker compose down -v`.

---

### Los logs del gateway muestran "Campo obligatorio faltante"

**Síntoma:** mensajes `WARNING — Campo obligatorio 'parcela' faltante`.

**Causa:** el simulador está enviando un mensaje malformado o vacío.

**Verificar:**
```bash
docker logs iot_simulator --tail 20
# Confirmar que el simulador está corriendo y publicando JSON válido
```

---

### `influxdb-client` da error de conexión rechazada

**Síntoma:** `urllib3.exceptions.NewConnectionError: Failed to establish connection`.

**Causa:** el gateway intentó escribir antes de que InfluxDB terminara de arrancar.
El healthcheck del docker-compose debería prevenir esto, pero en máquinas lentas puede fallar.

**Solución:**
```bash
docker compose restart gateway
```
---

## 17. Conexión con Fase 4

### Estado del sistema al finalizar Fase 3

| Componente | URL / Acceso | Datos |
|---|---|---|
| InfluxDB | `http://localhost:8086` | bucket `agro_iot_data`, measurement `sensor_data` |
| Gateway | `docker compose logs gateway` | en ejecución continua |
| Mosquitto | `localhost:1883` | topics `agricultura/sensores/<parcela>` |

### Qué debe hacer Fase 4 (procesamiento y alertas)

Fase 4 extiende el `gateway.py` con lógica de **validación, enriquecimiento y alertas**.
El agente que implemente Fase 4 debe modificar `on_message()` para agregar:

1. **Validación de rangos:** comparar cada field contra los umbrales del EDA Fase 1
2. **Enriquecimiento:** calcular campos derivados (ej. índice de estrés hídrico)
3. **Generación de alertas:** si se supera un umbral, publicar en `agricultura/alertas/<parcela>`
   y/o escribir en un segundo measurement `alertas` en el mismo bucket

### Umbrales del EDA Fase 1 para las alertas de Fase 4

| Variable | Caña — Alerta Baja | Caña — Alerta Alta | Palma — Alerta Baja | Palma — Alerta Alta |
|---|---|---|---|---|
| `temperature_air` (°C) | < 18 | > 38 | < 18 | > 35 |
| `humidity` (%) | < 55 | > 88 | < 60 | > 95 |
| `soil_moisture` (%) | **< 15** | > 40 | < 30 | > 55 |
| `soil_ph` | < 5.5 | > 8.5 | < 3.5 | > 6.5 |
| `rainfall` (mm) | < 900 | > 1900 | < 100 | > 210 |
| `solar_radiation` (MJ/m²) | < 12 | > 28 | < 12 | > 28 |
| `wind_speed` (km/h) | — | > 40 | — | > 40 |

> La humedad del suelo es el **indicador crítico más importante** (+13.2% diferencia
> Q4 vs Q1 en el EDA). La alerta de `soil_moisture < 15%` en caña debe ser la
> primera en implementarse en Fase 4.

### Esquema de topic para alertas (Fase 4)

```
agricultura/alertas/<parcela>

Payload:
{
  "timestamp": "2026-05-03 14:30:00",
  "parcela": "parcela_1",
  "cultivo": "sugarcane",
  "tipo_alerta": "SOIL_MOISTURE_LOW",
  "variable": "soil_moisture",
  "valor_actual": 12.3,
  "umbral": 15.0,
  "severidad": "CRITICA"
}
```

---

*Documento generado: Mayo 2026 — Universidad ICESI, Sistemas y Comunicaciones I*
