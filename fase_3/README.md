# Fase 3 — Ingestión y Almacenamiento de Datos IoT en InfluxDB

**Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026**

Gateway IoT en Python que suscribe al broker MQTT (Eclipse Mosquitto), recibe los mensajes JSON de los 4 sensores simulados, los valida, los transforma en puntos InfluxDB y los almacena en una base de datos de series temporales.

---

## Objetivo de la fase

Implementar el flujo de ingestión de datos crudos:

```
Sensores simulados (Fase 2)
        │
        │  MQTT  agricultura/sensores/<parcela>
        ▼
Eclipse Mosquitto :1883  (Broker)
        │
        ▼
Gateway IoT Python  (Edge Computing)
  ├── Recibe mensaje JSON por MQTT
  ├── Valida campos obligatorios
  ├── Transforma a Point InfluxDB
  └── Escribe en bucket agro_iot_data
        │
        ▼
InfluxDB :8086  →  bucket: agro_iot_data
```

---

## Estructura de archivos

```
fase_3/
├── docker-compose.yml           # Stack: Mosquitto + Simulador + InfluxDB + Gateway
├── mosquitto/
│   └── mosquitto.conf           # Broker MQTT (puerto 1883, anónimo)
└── gateway/
    ├── gateway.py               # Gateway Python (237 líneas)
    ├── Dockerfile
    └── requirements.txt
```

---

## Qué hace el gateway

### Pipeline por mensaje recibido

1. **Recibe** el payload JSON del broker MQTT (callback `on_message`)
2. **Valida** que estén presentes los campos obligatorios: `parcela`, `cultivo`, `timestamp`
3. **Parsea** cada campo de sensor como `float`; descarta los no numéricos con un warning
4. **Construye** un `Point` de InfluxDB con:
   - `measurement`: `sensor_data`
   - `tags`: `parcela`, `cultivo`, `area_ha`
   - `fields`: los sensores presentes en ese tick (payload parcial es válido)
   - `timestamp`: derivado del campo `timestamp` del JSON
5. **Escribe** en `bucket: agro_iot_data` con precisión nanosegundos

### Reconexión automática

El gateway reintenta la conexión MQTT hasta 15 veces con 3 segundos de pausa entre intentos. Una vez conectado, `loop_forever()` mantiene la conexión y gestiona reconexiones si el broker cae.

---

## Payload JSON recibido (ejemplo)

```json
{
  "timestamp": "2026-05-10 14:30:00",
  "parcela":   "parcela_1",
  "cultivo":   "sugarcane",
  "area_ha":   5.0,
  "temperature_air":  28.47,
  "humidity":         70.83,
  "rainfall":         1462.5,
  "soil_ph":          7.21,
  "soil_moisture":    26.8,
  "solar_radiation":  22.34
}
```

### Sensores reconocidos

`temperature_air` · `humidity` · `rainfall` · `soil_ph` · `soil_moisture` · `solar_radiation` · `wind_speed` · `evapotranspiration`

Cualquier otro campo del JSON es ignorado.

---

## Cómo ejecutarlo

### Prerequisitos

- Docker >= 24 y Docker Compose v2
- Datasets en `../datasets/`:
  - `sugarcane-prediction-dataset.csv`
  - `crop-production-countries.csv`

### Arrancar el stack

```bash
cd fase_3
docker compose up --build
```

Esto levanta 4 servicios en orden:

| Servicio | Imagen | Puerto | Depende de |
|----------|--------|--------|------------|
| `mosquitto` | eclipse-mosquitto:latest | 1883 | — |
| `simulator` | build: ../fase_2 | — | mosquitto healthy |
| `influxdb` | influxdb:2.7 | 8086 | — |
| `gateway` | build: ./gateway | — | influxdb + mosquitto healthy |

### Arrancar en segundo plano

```bash
docker compose up --build -d
docker compose logs -f gateway    # ver logs en tiempo real
```

### Detener

```bash
docker compose down               # conserva los datos
docker compose down -v            # borra volúmenes (resetea InfluxDB)
```

---

## Verificar que funciona

### 1. Logs del gateway

Deben aparecer líneas como:

```
[gateway] INFO — ✔ Conectado al broker MQTT mosquitto:1883
[gateway] INFO — Suscrito a topic: agricultura/sensores/#
[gateway] INFO — [parcela_1] sugarcane → InfluxDB | campos=['temperature_air', 'humidity', ...]
[gateway] INFO — [parcela_3] oil_palm  → InfluxDB | campos=['temperature_air', 'rainfall', ...]
```

```bash
docker compose logs -f gateway
```

### 2. Datos en InfluxDB

1. Abrir `http://localhost:8086`
2. Usuario: `admin` / Contraseña: `agro_admin_2026`
3. **Data Explorer** → bucket `agro_iot_data` → measurement `sensor_data`
4. Ejecutar la siguiente query Flux:

```flux
from(bucket: "agro_iot_data")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> limit(n: 20)
```

Deben aparecer registros con tags `parcela`, `cultivo`, `area_ha` y los campos de sensor.

### 3. Mensajes MQTT en vivo

```bash
docker compose exec mosquitto mosquitto_sub \
  -t "agricultura/sensores/#" -v -C 20
```

Muestra los primeros 20 mensajes con el topic y el payload JSON de cada parcela.

### 4. Estado de los contenedores

```bash
docker compose ps
```

Todos los servicios deben estar en estado `running`. InfluxDB y Mosquitto tienen healthchecks; si no aparecen como `healthy`, esperar ~30 segundos.

---

## Variables de entorno del gateway

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MQTT_BROKER` | `mosquitto` | Hostname del broker |
| `MQTT_PORT` | `1883` | Puerto MQTT |
| `MQTT_TOPIC` | `agricultura/sensores/#` | Topic de suscripción |
| `INFLUX_URL` | `http://influxdb:8086` | URL de InfluxDB |
| `INFLUX_TOKEN` | `agro-iot-token-fase3-icesi-2026` | Token de autenticación |
| `INFLUX_ORG` | `agricultura` | Organización |
| `INFLUX_BUCKET` | `agro_iot_data` | Bucket de escritura |

---

## Estructura de datos en InfluxDB

| Elemento | Valor |
|----------|-------|
| Measurement | `sensor_data` |
| Tag: parcela | `parcela_1` / `parcela_2` / `parcela_3` / `parcela_4` |
| Tag: cultivo | `sugarcane` / `oil_palm` |
| Tag: area_ha | `5.0` / `3.5` / `8.0` / `6.5` |
| Fields | `temperature_air`, `humidity`, `rainfall`, `soil_ph`, `soil_moisture`, `solar_radiation`, `wind_speed`, `evapotranspiration` |
| Precisión temporal | Nanosegundos (NS) |
| Retention | Infinita |

---

## Relación con otras fases

| Fase | Rol respecto a esta fase |
|------|--------------------------|
| Fase 2 | Genera y publica los mensajes MQTT que este gateway consume |
| Fase 4 | Refactoriza y extiende este gateway con pipeline de procesamiento, umbrales y variables derivadas |

> El gateway de esta fase es **monolítico** (un solo archivo, 237 líneas). La Fase 4 lo reemplaza con una arquitectura modular en `gateway_iot/` que aplica el principio de responsabilidad única (SRP).

---

## Troubleshooting

### "broker no disponible" en los logs

El gateway reintenta automáticamente 15 veces. Si persiste:

```bash
docker compose logs mosquitto
docker compose restart gateway
```

### InfluxDB no acepta escrituras

Verificar que el token sea correcto y que el healthcheck pase:

```bash
docker compose ps influxdb   # debe mostrar "healthy"
```

### No aparecen datos en InfluxDB después de 1 minuto

Verificar que el simulador esté publicando:

```bash
docker compose logs simulator | tail -20
```
