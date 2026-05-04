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
6. [Paso 2 — Dockerfile de Node-RED](#6-paso-2--dockerfile-de-node-red)
7. [Paso 3 — settings.js de Node-RED](#7-paso-3--settingsjs-de-node-red)
8. [Paso 4 — flows.json (flujo completo Node-RED)](#8-paso-4--flowsjson-flujo-completo-node-red)
9. [Paso 5 — Levantar todos los servicios](#9-paso-5--levantar-todos-los-servicios)
10. [Paso 6 — Verificar InfluxDB](#10-paso-6--verificar-influxdb)
11. [Paso 7 — Verificar Node-RED](#11-paso-7--verificar-node-red)
12. [Paso 8 — Verificar datos almacenados](#12-paso-8--verificar-datos-almacenados)
13. [Queries Flux de referencia](#13-queries-flux-de-referencia)
14. [Troubleshooting](#14-troubleshooting)
15. [Entregables para el profesor](#15-entregables-para-el-profesor)
16. [Conexión con Fase 4](#16-conexión-con-fase-4)

---

## 1. Contexto y punto de partida

### Qué existe ya (Fase 2)

La carpeta `fase_2/` contiene un simulador funcional con los siguientes servicios:

| Servicio | Imagen | Puerto | Estado |
|---|---|---|---|
| `mqtt_broker` | `eclipse-mosquitto:latest` | `1883` | ✅ Operativo |
| `iot_simulator` | imagen local | — | ✅ Operativo |

El simulador publica mensajes JSON cada 15/30/60 segundos en los siguientes topics MQTT:
- `agricultura/sensores/parcela_1` — Caña de azúcar, 5 ha
- `agricultura/sensores/parcela_2` — Caña de azúcar, 3.5 ha
- `agricultura/sensores/parcela_3` — Palma de aceite, 8 ha
- `agricultura/sensores/parcela_4` — Palma de aceite, 6.5 ha

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

### Qué falta construir (Fase 3)

```
[YA EXISTE]                [FASE 3 — CONSTRUIR]
Sensores IoT (Python)
       │
       ▼
Broker MQTT (Mosquitto) ──► Gateway IoT (Node-RED) ──► Raw Database (InfluxDB)
                                     │
                              - Recibe mensajes MQTT
                              - Parsea JSON
                              - Valida campos
                              - Transforma a formato
                                InfluxDB line protocol
                              - Escribe en bucket
```

---

## 2. Arquitectura de la fase

### Flujo completo de datos

```
simulator.py
    │ publica JSON cada 15-60 s
    ▼
eclipse-mosquitto:1883
    │ topic: agricultura/sensores/#
    ▼
Node-RED :1880
    │ nodo mqtt in → json → function → influxdb out
    ▼
InfluxDB :8086
    │ org: agricultura | bucket: agro_iot_data
    ▼
Data Explorer (UI web InfluxDB)
    │ Flux queries para verificación
    ▼
[Fase 4] Procesamiento y alertas
```

### Modelo de datos en InfluxDB

InfluxDB v2 usa el concepto de **measurement + tags + fields + timestamp**:

| Componente | Valor | Descripción |
|---|---|---|
| **measurement** | `sensor_data` | Nombre de la "tabla" en InfluxDB |
| **tag: parcela** | `parcela_1` … `parcela_4` | Indexed — para filtrar por parcela |
| **tag: cultivo** | `sugarcane` / `oil_palm` | Indexed — para filtrar por cultivo |
| **tag: area_ha** | `"5.0"` | Indexed — área de la parcela |
| **field: temperature_air** | `28.47` | Float — valor del sensor |
| **field: humidity** | `70.83` | Float |
| **field: rainfall** | `1462.5` | Float |
| **field: soil_ph** | `7.21` | Float |
| **field: soil_moisture** | `26.8` | Float |
| **field: solar_radiation** | `22.34` | Float |
| **field: wind_speed** | `8.61` | Float |
| **field: evapotranspiration** | `5.01` | Float |
| **timestamp** | nanoseconds epoch | Generado por Node-RED desde `payload.timestamp` |

> **Distinción clave:** Los `tags` son strings indexados (usados en filtros WHERE).
> Los `fields` son valores numéricos almacenados como series temporales.
> No invertir esta distinción — si se convierte un field en tag se degrada el rendimiento.

---

## 3. Stack tecnológico

| Tecnología | Versión | Rol | Puerto |
|---|---|---|---|
| Eclipse Mosquitto | `latest` | Broker MQTT | `1883` |
| Node-RED | `latest` + plugin | Gateway IoT (Edge Computing) | `1880` |
| `node-red-contrib-influxdb` | `npm latest` | Plugin para escribir en InfluxDB v2 | — |
| InfluxDB | `2.7` | Base de datos de series temporales (raw data) | `8086` |
| Python simulator | imagen local (Fase 2) | Fuente de datos | — |

### Credenciales fijas para el lab

> Estas credenciales son fijas y hardcodeadas para el entorno de laboratorio.
> **No usar en producción.**

| Parámetro | Valor |
|---|---|
| InfluxDB organización | `agricultura` |
| InfluxDB bucket | `agro_iot_data` |
| InfluxDB usuario admin | `admin` |
| InfluxDB contraseña admin | `agro_admin_2026` |
| InfluxDB API token | `agro-iot-token-fase3-icesi-2026` |
| Node-RED URL | `http://localhost:1880` |
| InfluxDB URL | `http://localhost:8086` |

---

## 4. Estructura de archivos a crear

El agente debe crear exactamente esta estructura dentro de `fase_3/`:

```
proyecto_final/
├── fase_2/                         ← ya existe, NO modificar
│   ├── docker-compose.yml
│   ├── simulator.py
│   └── ...
└── fase_3/                         ← crear todo aquí
    ├── plan_implementacion.md      ← este archivo
    ├── docker-compose.yml          ← TODOS los servicios (mosquitto+simulator+nodered+influxdb)
    ├── mosquitto/
    │   └── mosquitto.conf          ← igual al de fase_2
    ├── nodered/
    │   ├── Dockerfile              ← node-red + plugin influxdb
    │   ├── flows.json              ← flujo pre-configurado (importar directamente)
    │   └── settings.js             ← deshabilitar cifrado de credenciales
    └── influxdb/
        └── (directorio vacío — Docker lo gestiona con volumen)
```

> **Nota para el agente:** `fase_3/` debe ser **autocontenida**. Al ejecutar
> `docker compose up --build` desde dentro de `fase_3/`, todo el sistema debe
> funcionar sin depender de que `fase_2/` esté corriendo.

---

## 5. Paso 1 — docker-compose.yml

Crear el archivo `fase_3/docker-compose.yml` con el siguiente contenido **exacto**:

```yaml
version: "3.8"

# ─────────────────────────────────────────────────────────────────────────────
# Fase 3 — Ingestión IoT en InfluxDB via Node-RED
# Servicios: Mosquitto + Simulador + Node-RED + InfluxDB
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

  # ── 4. Gateway IoT — Node-RED ───────────────────────────────────────────────
  nodered:
    build:
      context: ./nodered
      dockerfile: Dockerfile
    container_name: nodered_gateway
    ports:
      - "1880:1880"
    depends_on:
      mosquitto:
        condition: service_healthy
      influxdb:
        condition: service_healthy
    environment:
      - TZ=America/Bogota
      - INFLUX_URL=http://influxdb:8086
      - INFLUX_TOKEN=agro-iot-token-fase3-icesi-2026
      - INFLUX_ORG=agricultura
      - INFLUX_BUCKET=agro_iot_data
    volumes:
      - ./nodered/flows.json:/data/flows.json:ro
      - ./nodered/settings.js:/data/settings.js:ro
      - nodered_data:/data
    restart: unless-stopped

volumes:
  mosquitto_data:
  mosquitto_log:
  influxdb_data:
  influxdb_config:
  nodered_data:
```

### Puntos críticos de este docker-compose

- `DOCKER_INFLUXDB_INIT_MODE=setup` hace que InfluxDB se auto-configure al primer inicio.
  Si el volumen `influxdb_data` ya existe, esta variable se ignora (no reconfigura).
- `DOCKER_INFLUXDB_INIT_RETENTION=0` significa retención infinita — los datos no se borran.
- Node-RED monta `flows.json` y `settings.js` como `:ro` (read-only) para evitar que
  Node-RED sobreescriba la configuración en el arranque.
- El simulador referencia `../fase_2` como contexto de build para reutilizar el código existente.

---

## 6. Paso 2 — Dockerfile de Node-RED

Crear `fase_3/nodered/Dockerfile` con el siguiente contenido:

```dockerfile
FROM nodered/node-red:latest

# Instalar el plugin de InfluxDB v2 para Node-RED
# node-red-contrib-influxdb soporta InfluxDB 1.x y 2.x
RUN npm install --unsafe-perm node-red-contrib-influxdb

# El directorio de trabajo de Node-RED es /data
# flows.json y settings.js se montan como volúmenes desde docker-compose
```

> **Por qué este Dockerfile:** La imagen oficial de Node-RED no incluye el plugin
> `node-red-contrib-influxdb`. Si se instala en tiempo de ejecución (desde la UI),
> requiere reiniciar el contenedor y no es reproducible. Pre-instalarlo en la imagen
> garantiza que el nodo `influxdb out` esté disponible cuando se cargue el flujo.

---

## 7. Paso 3 — settings.js de Node-RED

Crear `fase_3/nodered/settings.js` con el siguiente contenido:

```javascript
module.exports = {
    // Deshabilitar cifrado de credenciales para entorno de laboratorio.
    // Esto permite que el token de InfluxDB en flows.json sea leído en texto plano.
    // NUNCA usar credentialSecret: false en producción.
    credentialSecret: false,

    // Directorio donde Node-RED guarda flows, credenciales y contexto
    userDir: '/data',

    // Puerto de la interfaz web
    uiPort: process.env.PORT || 1880,

    // Zona horaria
    functionGlobalContext: {
        TZ: process.env.TZ || 'America/Bogota'
    },

    // Logging detallado para debugging
    logging: {
        console: {
            level: "info",
            metrics: false,
            audit: false
        }
    },

    // Deshabilitar el editor en producción (opcional — dejarlo habilitado para el lab)
    disableEditor: false,

    // Habilitar el panel de debug
    debugMaxLength: 1000,
}
```

---

## 8. Paso 4 — flows.json (flujo completo Node-RED)

Este es el archivo más importante. Contiene el flujo Node-RED pre-configurado que
implementa el pipeline: `MQTT → JSON → Validación → InfluxDB`.

Crear `fase_3/nodered/flows.json` con el siguiente contenido **exacto**:

```json
[
  {
    "id": "tab_fase3_agro",
    "type": "tab",
    "label": "Ingesta IoT Agrícola — Fase 3",
    "disabled": false,
    "info": "Pipeline: MQTT (Mosquitto) → Parse JSON → Validar + Transformar → InfluxDB\nTopics: agricultura/sensores/#\nMeasurement: sensor_data\nBucket: agro_iot_data"
  },
  {
    "id": "cfg_mqtt_broker",
    "type": "mqtt-broker",
    "name": "Mosquitto Agro",
    "broker": "mosquitto",
    "port": "1883",
    "clientid": "nodered_gateway_agro",
    "autoConnect": true,
    "usetls": false,
    "protocolVersion": "4",
    "keepalive": "60",
    "cleansession": true,
    "birthTopic": "",
    "birthQos": "0",
    "birthRetain": "false",
    "birthPayload": "",
    "closeTopic": "",
    "closeQos": "0",
    "closeRetain": "false",
    "closePayload": "",
    "willTopic": "",
    "willQos": "0",
    "willRetain": "false",
    "willPayload": ""
  },
  {
    "id": "cfg_influxdb",
    "type": "influxdb",
    "hostname": "influxdb",
    "port": "8086",
    "protocol": "http",
    "database": "agro_iot_data",
    "name": "InfluxDB Agricultura",
    "usetls": false,
    "influxdbVersion": "2.0",
    "url": "http://influxdb:8086",
    "rejectUnauthorized": false,
    "token": "agro-iot-token-fase3-icesi-2026",
    "org": "agricultura",
    "bucket": "agro_iot_data"
  },
  {
    "id": "node_mqtt_in",
    "type": "mqtt in",
    "z": "tab_fase3_agro",
    "name": "Sensores IoT — Todas las parcelas",
    "topic": "agricultura/sensores/#",
    "qos": "1",
    "datatype": "utf8",
    "broker": "cfg_mqtt_broker",
    "nl": false,
    "rap": false,
    "rh": 0,
    "inputs": 0,
    "x": 160,
    "y": 200,
    "wires": [["node_json_parse"]]
  },
  {
    "id": "node_json_parse",
    "type": "json",
    "z": "tab_fase3_agro",
    "name": "Parse JSON",
    "property": "payload",
    "action": "obj",
    "pretty": false,
    "x": 390,
    "y": 200,
    "wires": [["node_transform"]]
  },
  {
    "id": "node_transform",
    "type": "function",
    "z": "tab_fase3_agro",
    "name": "Validar + Transformar → InfluxDB",
    "func": "const p = msg.payload;\n\n// ── Validación de campos obligatorios ─────────────────────────────────\nif (!p || typeof p !== 'object') {\n    node.warn('Payload vacío o no es objeto');\n    return null;\n}\nif (!p.parcela || !p.cultivo || !p.timestamp) {\n    node.warn('Campos obligatorios faltantes: ' + JSON.stringify(p));\n    return null;\n}\n\n// ── Construir fields solo con sensores presentes en el payload ─────────\nconst SENSOR_FIELDS = [\n    'temperature_air', 'humidity', 'rainfall',\n    'soil_ph', 'soil_moisture', 'solar_radiation',\n    'wind_speed', 'evapotranspiration'\n];\n\nconst fields = {};\nfor (const f of SENSOR_FIELDS) {\n    const v = p[f];\n    if (v !== undefined && v !== null && !isNaN(parseFloat(v))) {\n        fields[f] = parseFloat(v);\n    }\n}\n\nif (Object.keys(fields).length === 0) {\n    node.warn('Mensaje sin campos de sensores válidos: ' + JSON.stringify(p));\n    return null;\n}\n\n// ── Convertir timestamp string → nanosegundos (InfluxDB requiere ns) ──\n// payload.timestamp formato: 'YYYY-MM-DD HH:MM:SS'\nlet tsNs;\ntry {\n    const tsMs = new Date(p.timestamp.replace(' ', 'T')).getTime();\n    if (isNaN(tsMs)) throw new Error('timestamp inválido');\n    tsNs = tsMs * 1000000;  // milisegundos → nanosegundos\n} catch(e) {\n    node.warn('Error parseando timestamp: ' + p.timestamp);\n    tsNs = Date.now() * 1000000;  // fallback: timestamp actual\n}\n\n// ── Estructura que espera node-red-contrib-influxdb (array de puntos) ─\nmsg.payload = [\n    {\n        measurement: 'sensor_data',\n        tags: {\n            parcela:  p.parcela,\n            cultivo:  p.cultivo,\n            area_ha:  String(p.area_ha || '')\n        },\n        fields: fields,\n        timestamp: tsNs\n    }\n];\n\n// Pasar topic como metadata para debugging\nmsg.topic = p.parcela;\n\nreturn msg;",
    "outputs": 1,
    "noerr": 0,
    "initialize": "",
    "finalize": "",
    "libs": [],
    "x": 650,
    "y": 200,
    "wires": [["node_influxdb_out", "node_debug_ok"]]
  },
  {
    "id": "node_influxdb_out",
    "type": "influxdb out",
    "z": "tab_fase3_agro",
    "influxdb": "cfg_influxdb",
    "name": "Escribir en InfluxDB",
    "measurement": "sensor_data",
    "precision": "ns",
    "retentionPolicy": "",
    "database": "agro_iot_data",
    "precisionV18FluxV20": "ns",
    "retentionPolicyV18Flux": "",
    "org": "agricultura",
    "bucket": "agro_iot_data",
    "x": 940,
    "y": 180,
    "wires": []
  },
  {
    "id": "node_debug_ok",
    "type": "debug",
    "z": "tab_fase3_agro",
    "name": "Debug — payload enviado a InfluxDB",
    "active": true,
    "tosidebar": true,
    "console": false,
    "tostatus": false,
    "complete": "payload",
    "targetType": "msg",
    "statusVal": "",
    "statusType": "auto",
    "x": 980,
    "y": 220,
    "wires": []
  },
  {
    "id": "node_catch_all",
    "type": "catch",
    "z": "tab_fase3_agro",
    "name": "Capturar errores del flujo",
    "scope": null,
    "uncaught": false,
    "x": 180,
    "y": 340,
    "wires": [["node_debug_error"]]
  },
  {
    "id": "node_debug_error",
    "type": "debug",
    "z": "tab_fase3_agro",
    "name": "Error Log",
    "active": true,
    "tosidebar": true,
    "console": false,
    "tostatus": false,
    "complete": "true",
    "targetType": "full",
    "statusVal": "",
    "statusType": "auto",
    "x": 420,
    "y": 340,
    "wires": []
  },
  {
    "id": "node_comment_arch",
    "type": "comment",
    "z": "tab_fase3_agro",
    "name": "ARQUITECTURA: Sensores IoT → Mosquitto :1883 → Node-RED → InfluxDB :8086 | bucket: agro_iot_data | org: agricultura",
    "info": "",
    "x": 500,
    "y": 80,
    "wires": []
  }
]
```

### Explicación de cada nodo del flujo

| Nodo | Tipo | Función |
|---|---|---|
| `cfg_mqtt_broker` | `mqtt-broker` | Config reutilizable: apunta a `mosquitto:1883` (hostname interno Docker) |
| `cfg_influxdb` | `influxdb` | Config reutilizable: URL, token, org, bucket para InfluxDB v2 |
| `node_mqtt_in` | `mqtt in` | Suscribe a `agricultura/sensores/#` — recibe mensajes de las 4 parcelas |
| `node_json_parse` | `json` | Convierte el string JSON del payload MQTT a objeto JavaScript |
| `node_transform` | `function` | Valida campos, construye structure InfluxDB, convierte timestamp a nanosegundos |
| `node_influxdb_out` | `influxdb out` | Escribe el punto en InfluxDB usando la config `cfg_influxdb` |
| `node_debug_ok` | `debug` | Muestra en sidebar de Node-RED cada payload escrito (para verificación) |
| `node_catch_all` | `catch` | Captura cualquier error en el flujo y lo redirige al log de errores |
| `node_debug_error` | `debug` | Muestra errores del flujo en el sidebar |

### Lógica clave del nodo `function` (node_transform)

```
Input:  msg.payload = { timestamp, parcela, cultivo, area_ha, temperature_air, humidity, ... }
        msg.topic   = "agricultura/sensores/parcela_1"

Proceso:
  1. Validar que existan: parcela, cultivo, timestamp
  2. Construir fields{} solo con los sensores que llegaron en este tick
     (no todos llegan en cada mensaje — depende de la frecuencia del sensor)
  3. Convertir timestamp "YYYY-MM-DD HH:MM:SS" → nanosegundos epoch
  4. Armar array de puntos para node-red-contrib-influxdb

Output: msg.payload = [
  {
    measurement: "sensor_data",
    tags:   { parcela, cultivo, area_ha },
    fields: { temperature_air: 28.47, humidity: 70.83, ... },
    timestamp: 1746280200000000000  // nanosegundos
  }
]
```

> **Por qué array:** `node-red-contrib-influxdb` acepta un array de puntos para
> escritura en batch. Aunque aquí solo se escribe 1 punto por mensaje, usar el
> formato array es compatible con versiones futuras que quieran hacer batching.

---

## 9. Paso 5 — Levantar todos los servicios

### Crear también el mosquitto.conf

Crear `fase_3/mosquitto/mosquitto.conf` con el siguiente contenido
(idéntico al de fase_2):

```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_type all
```

### Comando de arranque

```bash
# Desde la carpeta fase_3/
cd fase_3

# Primera vez: construir imágenes y levantar todos los servicios
docker compose up --build

# Ejecución sin rebuild (después del primer arranque)
docker compose up

# En background (para dejar corriendo y ver logs por separado)
docker compose up --build -d
docker compose logs -f
```

### Orden de arranque esperado (healthchecks garantizan el orden)

```
1. mosquitto      → arranca primero (broker)
2. influxdb       → arranca y ejecuta DOCKER_INFLUXDB_INIT_MODE=setup (crea org + bucket + token)
3. simulator      → espera mosquitto healthy, empieza a publicar
4. nodered        → espera mosquitto + influxdb healthy, carga flows.json, conecta al broker
```

### Qué ver en los logs al arrancar correctamente

```
influxdb_agro    | ts=... lvl=info msg="Welcome to InfluxDB" ...
influxdb_agro    | ts=... lvl=info msg="Listening" log_id=... service=tcp-listener ...
nodered_gateway  | [info] Starting flows
nodered_gateway  | [info] Started flows
nodered_gateway  | [info] [mqtt in:Sensores IoT] Connected to broker: mqtt://mosquitto:1883
iot_simulator    | ✔ Conectado al broker MQTT mosquitto:1883
iot_simulator    | ▶  parcela_1 | cultivo=sugarcane  | área=5.0 ha | ...
```

---

## 10. Paso 6 — Verificar InfluxDB

### Verificar que InfluxDB está corriendo

```bash
# Desde el host
curl -s http://localhost:8086/ping
# Respuesta esperada: HTTP 204 (sin body)

# O usando influx CLI dentro del contenedor
docker exec influxdb_agro influx ping
# Respuesta esperada: OK
```

### Verificar org y bucket creados

```bash
docker exec influxdb_agro influx org list \
  --token agro-iot-token-fase3-icesi-2026
# Debe mostrar: ID  Name → agricultura

docker exec influxdb_agro influx bucket list \
  --token agro-iot-token-fase3-icesi-2026 \
  --org agricultura
# Debe mostrar: agro_iot_data | infinite retention
```

### Acceder a la UI web de InfluxDB

1. Abrir `http://localhost:8086`
2. Iniciar sesión: usuario `admin`, contraseña `agro_admin_2026`
3. Navegar a **Data → Buckets** → verificar que existe `agro_iot_data`
4. Navegar a **Data → API Tokens** → verificar el token `agro-iot-token-fase3-icesi-2026`

---

## 11. Paso 7 — Verificar Node-RED

### Acceder a la interfaz web

1. Abrir `http://localhost:1880`
2. Verificar que el flujo **"Ingesta IoT Agrícola — Fase 3"** está cargado
3. El nodo `mqtt in` debe mostrar el indicador verde **"connected"**
4. El nodo `influxdb out` debe mostrar el indicador verde sin errores

### Verificar mensajes llegando en tiempo real

En la interfaz de Node-RED:
1. Hacer clic en el tab **Debug** (ícono de bicho en el panel derecho)
2. Cada 15 segundos debe aparecer un nuevo payload del estilo:
   ```json
   [
     {
       "measurement": "sensor_data",
       "tags": { "parcela": "parcela_1", "cultivo": "sugarcane", "area_ha": "5" },
       "fields": { "temperature_air": 28.47, "humidity": 70.83, ... },
       "timestamp": 1746280200000000000
     }
   ]
   ```

### Si el nodo MQTT muestra "disconnected"

```bash
# Verificar que mosquitto está corriendo
docker ps | grep mqtt_broker
# Si el contenedor existe pero está unhealthy:
docker logs mqtt_broker --tail 20
```

### Si el nodo InfluxDB muestra error

```bash
# Verificar conectividad desde Node-RED hacia InfluxDB
docker exec nodered_gateway wget -qO- http://influxdb:8086/ping
# Respuesta esperada: silencio (HTTP 204 sin body)
```

---

## 12. Paso 8 — Verificar datos almacenados

### Opción A — Data Explorer (UI web de InfluxDB)

1. Ir a `http://localhost:8086`
2. Navegar a **Explore**
3. En el panel izquierdo seleccionar:
   - **Bucket:** `agro_iot_data`
   - **Measurement:** `sensor_data`
   - **Field:** `temperature_air` (o cualquier otro)
4. Hacer clic en **Submit**
5. Deben aparecer series temporales con datos de las 4 parcelas

### Opción B — Flux query en el Data Explorer

Ir a **Explore → Script Editor** y ejecutar:

```flux
// Últimos 10 minutos de todos los sensores
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
  '
from(bucket: "agro_iot_data")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> limit(n: 10)
  '
```

**Resultado esperado:** tabla con columnas `_time`, `_measurement`, `_field`, `_value`,
`parcela`, `cultivo` y valores numéricos de sensores.

---

## 13. Queries Flux de referencia

Estas queries son útiles para demostración al profesor y para Fase 4.

### Query 1 — Últimas lecturas por parcela

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

### Query 3 — Comparar humedad suelo caña vs palma

```flux
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

### Query 5 — Detectar temperatura fuera de rango óptimo (pre-alerta)

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

## 14. Troubleshooting

### Problema: Node-RED no conecta a Mosquitto

**Síntoma:** Nodo `mqtt in` muestra rojo / "disconnected"

**Causa:** Node-RED arrancó antes de que Mosquitto estuviera listo.

**Solución:**
```bash
# Reiniciar solo Node-RED (el broker sigue corriendo)
docker compose restart nodered
# Esperar 10 segundos y verificar en http://localhost:1880
```

---

### Problema: InfluxDB no recibe datos (nodo influxdb out no cambia de estado)

**Síntoma:** Debug panel de Node-RED muestra payloads correctos pero InfluxDB está vacío.

**Causa más común:** Token incorrecto o mismatch entre flows.json y la config de InfluxDB.

**Verificación:**
```bash
# Probar el token directamente
curl -s \
  -H "Authorization: Token agro-iot-token-fase3-icesi-2026" \
  http://localhost:8086/api/v2/buckets?org=agricultura
# Debe devolver JSON con el bucket agro_iot_data
```

**Solución:** Si el token no funciona, InfluxDB ya fue inicializado con uno diferente
(el volumen `influxdb_data` persiste la config). Eliminar el volumen y reiniciar:
```bash
docker compose down -v   # -v elimina los volúmenes
docker compose up --build
```

---

### Problema: flows.json se sobreescribe al modificar el flujo en la UI

**Síntoma:** Cambios en la UI de Node-RED se pierden al reiniciar.

**Causa:** El archivo `flows.json` está montado como `:ro` (read-only).

**Solución (si se quieren persistir cambios de la UI):**
1. Cambiar el volumen en docker-compose de `:ro` a `rw`
2. O exportar el flujo desde la UI: `Menu → Export → Download`
3. Reemplazar `fase_3/nodered/flows.json` con el exportado

---

### Problema: `DOCKER_INFLUXDB_INIT_MODE=setup` da error al reiniciar

**Síntoma:** `influxdb_agro` falla al arrancar con mensaje de "already initialized".

**Causa:** El volumen `influxdb_data` ya contiene una instalación previa.

**Solución:** Este error es inofensivo — InfluxDB funciona igualmente.
Si se quiere limpiar por completo:
```bash
docker compose down -v
docker compose up --build
```

---

### Problema: Node-RED muestra "Cannot read properties of undefined"

**Síntoma:** Error en el nodo `function` en el debug panel.

**Causa:** El payload MQTT llegó como string vacío o el JSON estaba malformado.

**Solución:** El nodo `function` ya tiene validación. Verificar que el simulador esté
corriendo correctamente:
```bash
docker logs iot_simulator --tail 20
```

---

## 15. Entregables para el profesor

Según la rúbrica del trabajo final (Fase 3 = 15% de la nota), los entregables son:

### Evidencia 1 — Captura del flujo en Node-RED

**Cómo obtenerla:**
1. Abrir `http://localhost:1880`
2. Tomar screenshot del flujo completo mostrando:
   - Los nodos conectados (MQTT in → JSON → Function → InfluxDB out)
   - El nodo `mqtt in` con indicador verde "connected"
   - El panel Debug con mensajes llegando en tiempo real

### Evidencia 2 — Configuración del Broker MQTT

**Cómo obtenerla:**
```bash
# Mostrar mensajes llegando al broker
docker exec -it mqtt_broker mosquitto_sub -t "agricultura/sensores/#" -v
# Tomar screenshot con JSON visible en terminal
```

### Evidencia 3 — Base de datos creada en InfluxDB

**Cómo obtenerla:**
1. Abrir `http://localhost:8086`
2. Ir a **Data → Buckets**
3. Tomar screenshot mostrando `agro_iot_data` con su organización `agricultura`

### Evidencia 4 — Almacenamiento de datos

**Cómo obtenerla:**
1. En InfluxDB → **Explore**
2. Ejecutar la Query 4 (contar registros por parcela) después de 5+ minutos de simulación
3. Tomar screenshot del resultado mostrando registros de las 4 parcelas

### Evidencia 5 — Consulta que muestre registros

**Cómo obtenerla:**
1. En InfluxDB → **Explore → Script Editor**
2. Pegar y ejecutar la Query 1 (últimas lecturas por parcela)
3. Tomar screenshot del gráfico o tabla resultante

### Checklist de entregables

```
□ Screenshot del flujo Node-RED completo con nodos conectados
□ Screenshot del panel Debug de Node-RED con payloads en tiempo real
□ Screenshot de mosquitto_sub mostrando JSON de al menos 2 parcelas distintas
□ Screenshot de InfluxDB → Buckets mostrando agro_iot_data
□ Screenshot de InfluxDB → Explore con datos de las 4 parcelas
□ Screenshot de la Query 3 (comparar humedad suelo caña vs palma) — demuestra que
  los datos son diferentes entre cultivos
□ Código fuente: fase_3/docker-compose.yml, nodered/flows.json, nodered/Dockerfile
```

> **Captura clave para nota máxima:** La Query 3 demuestra que los datos de caña y
> palma son distintos (pH 4–6 vs 6–8.5, humedad suelo 30–55% vs 10–40%).
> Esto valida que la Fase 2 tiene dos fuentes de datos reales separadas.

---

## 16. Conexión con Fase 4

La Fase 4 extiende lo construido aquí con **procesamiento, limpieza y alertas**.
El agente que implemente la Fase 4 debe saber:

### Qué existe al final de la Fase 3

| Componente | URL | Datos |
|---|---|---|
| InfluxDB | `http://localhost:8086` | bucket `agro_iot_data`, measurement `sensor_data` |
| Node-RED | `http://localhost:1880` | flujo de ingesta activo |
| Mosquitto | `localhost:1883` | topics `agricultura/sensores/<parcela>` |

### Umbrales definidos en el EDA (Fase 1) para las alertas de Fase 4

| Variable | Caña — Alerta Baja | Caña — Alerta Alta | Palma — Alerta Baja | Palma — Alerta Alta |
|---|---|---|---|---|
| `temperature_air` | < 18 °C | > 38 °C | < 18 °C | > 35 °C |
| `humidity` | < 55% | > 88% | < 60% | > 95% |
| `soil_moisture` | **< 15%** | > 40% | < 30% | > 55% |
| `soil_ph` | < 5.5 | > 8.5 | < 3.5 | > 6.5 |
| `rainfall` | < 900 mm | > 1900 mm | < 100 mm/mes | > 210 mm/mes |
| `solar_radiation` | < 12 | > 28 | < 12 | > 28 |
| `wind_speed` | — | > 40 km/h | — | > 40 km/h |

> La humedad del suelo es el **indicador operacional más crítico** (mayor
> discriminador Q4 vs Q1, +13.2% diferencia según EDA Fase 1).

### Cómo extender el flujo Node-RED en Fase 4

En Fase 4 se debe agregar, **después del nodo `function`**, una rama adicional con:
- Nodo `switch` → evalúa si algún field supera los umbrales
- Nodo `function` → construye alerta JSON con `{ tipo, parcela, variable, valor, umbral, timestamp }`
- Nodo `mqtt out` → publica la alerta en `agricultura/alertas/<parcela>`
- Nodo `influxdb out` → escribe la alerta en un segundo measurement `alertas` dentro
  del mismo bucket `agro_iot_data`

---

*Documento generado: Mayo 2026 — Universidad ICESI, Sistemas y Comunicaciones I*
