# Gateway IoT Agrícola — Fases 4, 5 y 7

Sistema de monitoreo agroclimático en tiempo real construido sobre MQTT, InfluxDB y Grafana.  
Procesa datos de 4 parcelas agrícolas (caña de azúcar y palma de aceite), detecta violaciones de umbrales y los visualiza en un dashboard pre-configurado.

> **Proyecto:** Trabajo Final — Sistemas y Comunicaciones I  
> **Universidad ICESI — Mayo 2026**

---

## Tabla de contenidos

1. [Contexto del proyecto](#1-contexto-del-proyecto)
2. [Qué implementa este módulo](#2-qué-implementa-este-módulo)
3. [Arquitectura](#3-arquitectura)
4. [Estructura de archivos](#4-estructura-de-archivos)
5. [Flujo de datos](#5-flujo-de-datos)
6. [Lógica de procesamiento](#6-lógica-de-procesamiento)
7. [Umbrales agroclimáticos](#7-umbrales-agroclimáticos)
8. [Infraestructura Docker](#8-infraestructura-docker)
9. [Cómo ejecutarlo](#9-cómo-ejecutarlo)
10. [Verificación end-to-end](#10-verificación-end-to-end)
11. [Dashboard Grafana](#11-dashboard-grafana)
12. [Configurar alertas por correo](#12-configurar-alertas-por-correo)
13. [Variables de entorno](#13-variables-de-entorno)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Contexto del proyecto

El proyecto completo consta de 7 fases:

| Fase | Descripción | Ubicación |
|------|-------------|-----------|
| 1 | Análisis exploratorio del dataset agroclimático | `fase_1/` |
| 2 | Simulador de sensores IoT publicando por MQTT | `fase_2/` |
| 3 | Gateway monolítico que escribe datos crudos en InfluxDB | `fase_3/` |
| **4** | **Pipeline de procesamiento en tiempo real** | **`gateway_iot/`** |
| **5** | **Verificación de umbrales y generación de alertas** | **`gateway_iot/`** |
| 6 | Machine Learning predictivo | *(pendiente)* |
| **7** | **Visualización con Grafana** | **`gateway_iot/`** |

Este directorio (`gateway_iot/`) implementa las fases 4, 5 y 7 en un único proyecto Python contenerizado que **reemplaza** al gateway monolítico de la fase 3.

---

## 2. Qué implementa este módulo

### Fase 4 — Pipeline de procesamiento en tiempo real

Refactorización completa del gateway de la fase 3 aplicando el principio de responsabilidad única (SRP). Cada clase tiene una sola función:

- **`DataValidator`** — valida campos obligatorios y rangos físicos de cada sensor.
- **`DataEnricher`** — calcula variables derivadas: `heat_stress_index`, `water_stress_flag` y `quality_score`.
- **`DataPipeline`** — orquesta el flujo completo en orden: validar → enriquecer → detectar alertas → escribir.

Los datos se escriben en **tres buckets separados** en InfluxDB, diferenciando datos crudos, procesados y eventos de alerta.

### Fase 5 — Umbrales y generación de alertas

- **`AlertChecker`** compara cada lectura contra los umbrales definidos en `config/thresholds.py`, derivados del análisis EDA de la fase 1.
- Clasifica cada violación como `warning` (exceso ≤ 20% del umbral) o `critical` (exceso > 20%).
- Las alertas se escriben en InfluxDB como eventos con tags de parcela, cultivo, variable y severidad.
- Grafana las consume y las pinta como anotaciones verticales en todos los paneles de tiempo.

### Fase 7 — Visualización con Grafana

- Grafana arranca ya configurado con datasource e InfluxDB conectado automáticamente.
- Dashboard "Monitoreo Agroclimático IoT" disponible en `http://localhost:3000` sin configuración manual.
- 4 filas de paneles: estado actual, series de tiempo, variables de suelo y radiación, e indicadores de estrés.
- Soporte opcional de alertas por correo Gmail (SMTP).

---

## 3. Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                           │
│                                                                 │
│  ┌──────────┐    MQTT     ┌──────────────────────────────────┐  │
│  │Simulador │──publish──▶│        Gateway IoT (Python)       │  │
│  │ fase_2   │            │                                    │  │
│  └──────────┘            │  MQTTClient                        │  │
│        ▲                 │    └─▶ DataPipeline                │  │
│        │                 │          ├─▶ DataValidator          │  │
│  ┌─────┴────┐            │          ├─▶ DataEnricher           │  │
│  │Mosquitto │            │          ├─▶ AlertChecker           │  │
│  │  :1883   │            │          └─▶ InfluxWriter           │  │
│  └──────────┘            └──────────────┬───────────────────┘  │
│                                         │                       │
│                          ┌──────────────▼───────────────────┐  │
│                          │         InfluxDB :8086            │  │
│                          │  ┌────────────────────────────┐   │  │
│                          │  │ bucket: agro_iot_data       │   │  │
│                          │  │ bucket: agro_iot_processed  │   │  │
│                          │  │ bucket: agro_iot_alerts     │   │  │
│                          │  └────────────────────────────┘   │  │
│                          └──────────────┬───────────────────┘  │
│                                         │ Flux queries          │
│                          ┌──────────────▼───────────────────┐  │
│                          │         Grafana :3000             │  │
│                          │  Dashboard pre-provisionado       │  │
│                          │  Anotaciones de alertas           │  │
│                          │  Email SMTP (opcional)            │  │
│                          └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Parcelas simuladas

| Parcela | Cultivo | Área | Sensores |
|---------|---------|------|----------|
| parcela_1 | Caña de azúcar | 5.0 ha | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_2 | Caña de azúcar | 3.5 ha | temperature_air, humidity, rainfall, wind_speed, evapotranspiration |
| parcela_3 | Palma de aceite | 8.0 ha | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_4 | Palma de aceite | 6.5 ha | temperature_air, humidity, rainfall, wind_speed |

---

## 4. Estructura de archivos

```
gateway_iot/
├── main.py                          # Entry point
├── Dockerfile                       # Imagen del gateway
├── docker-compose.yml               # Stack completo (5 servicios)
├── requirements.txt
├── .env.example                     # Plantilla de variables de entorno
│
├── config/
│   ├── settings.py                  # Carga todas las env vars con defaults
│   └── thresholds.py                # Umbrales por cultivo + rangos físicos
│
├── models/
│   └── sensor_reading.py            # Dataclasses SensorReading y AlertEvent
│
├── core/
│   ├── mqtt_client.py               # Conexión MQTT, suscripción, callbacks
│   ├── influx_writer.py             # Escritura en los 3 buckets; crea buckets si no existen
│   └── pipeline.py                  # Orquesta: validate → enrich → alerts → write
│
├── processors/
│   ├── validator.py                 # Valida campos obligatorios y rangos físicos
│   ├── enricher.py                  # Calcula heat_stress_index, water_stress_flag, quality_score
│   └── alert_checker.py             # Compara contra thresholds, clasifica warning/critical
│
├── mosquitto/
│   └── mosquitto.conf               # Configuración del broker MQTT
│
└── grafana/
    ├── grafana.ini                  # Config Grafana (SMTP con placeholders)
    └── provisioning/
        ├── datasources/
        │   └── influxdb.yaml        # Datasources InfluxDB (Flux)
        └── dashboards/
            ├── dashboard.yaml       # Loader automático de dashboards
            └── agro_dashboard.json  # Dashboard completo con 13 paneles
```

---

## 5. Flujo de datos

Cada mensaje MQTT recibido atraviesa el siguiente pipeline:

```
Broker MQTT
    │
    │  JSON payload:
    │  { "timestamp": "2026-05-10 10:00:00",
    │    "parcela": "parcela_1", "cultivo": "sugarcane",
    │    "temperature_air": 28.5, "humidity": 70.0, ... }
    │
    ▼
MQTTClient.on_message()
    │
    ▼
DataPipeline.process()
    │
    ├─▶ DataValidator.validate()
    │       • Verifica campos obligatorios: parcela, cultivo, timestamp
    │       • Verifica que cada valor numérico esté dentro del rango físico del sensor
    │       • Valores fuera de rango se anotan en invalid_fields (no se descartan)
    │       • Retorna SensorReading (o None si faltan campos obligatorios)
    │
    ├─▶ DataEnricher.enrich()
    │       • heat_stress_index = 1.0 si temperature_air > umbral_alto, 0.0 si no
    │       • water_stress_flag = 1.0 si soil_moisture < umbral_bajo, 0.0 si no
    │       • quality_score = campos_válidos / (campos_válidos + campos_inválidos)
    │
    ├─▶ AlertChecker.check()
    │       • Itera campos del SensorReading
    │       • Compara contra THRESHOLDS[cultivo][campo]
    │       • Si viola umbral bajo: calcula exceso = (low - value) / low
    │       • Si viola umbral alto: calcula exceso = (value - high) / high
    │       • exceso > 20% → severity="critical" | exceso ≤ 20% → severity="warning"
    │       • Retorna List[AlertEvent]
    │
    └─▶ InfluxWriter
            • write_raw()       → bucket agro_iot_data       (datos tal como llegaron)
            • write_processed() → bucket agro_iot_processed  (datos + derivadas)
            • write_alerts()    → bucket agro_iot_alerts      (uno por AlertEvent)
```

---

## 6. Lógica de procesamiento

### Variables derivadas (DataEnricher)

| Campo | Tipo | Lógica |
|-------|------|--------|
| `heat_stress_index` | float (0.0 / 1.0) | 1.0 si `temperature_air` supera el umbral alto del cultivo |
| `water_stress_flag` | float (0.0 / 1.0) | 1.0 si `soil_moisture` cae bajo el umbral bajo del cultivo |
| `quality_score` | float (0.0 – 1.0) | `campos_válidos / (campos_válidos + campos_inválidos)` |

### Clasificación de severidad (AlertChecker)

```
exceso_porcentual = |valor - umbral| / |umbral| × 100

exceso > 20%  →  severity = "critical"
exceso ≤ 20%  →  severity = "warning"
```

Ejemplo:
- `soil_moisture = 10.0`, umbral bajo = 15.0 → déficit = 33% → **critical**
- `temperature_air = 39.0`, umbral alto = 38.0 → exceso = 2.6% → **warning**

### Tres buckets en InfluxDB

| Bucket | Contenido | Retention |
|--------|-----------|-----------|
| `agro_iot_data` | Datos crudos del simulador (measurement: `sensor_data`) | Infinita |
| `agro_iot_processed` | Datos validados + `heat_stress_index`, `water_stress_flag`, `quality_score` | Infinita |
| `agro_iot_alerts` | Eventos de alerta (measurement: `alert_events`) | 30 días |

> `agro_iot_data` lo crea InfluxDB en el primer arranque.  
> `agro_iot_processed` y `agro_iot_alerts` los crea el gateway automáticamente usando `BucketsApi` al iniciar.

---

## 7. Umbrales agroclimáticos

Definidos en `config/thresholds.py`. Fuente: análisis EDA fase 1 (secciones 7.1 y 7.2).

### Caña de azúcar (`sugarcane`)

| Variable | Alerta baja | Alerta alta | Unidad |
|----------|-------------|-------------|--------|
| temperature_air | < 18.0 | > 38.0 | °C |
| rainfall | < 900.0 | > 1900.0 | mm/mes |
| humidity | < 55.0 | > 88.0 | % |
| soil_ph | < 5.5 | > 8.5 | pH |
| soil_moisture | < 15.0 | > 40.0 | % |
| solar_radiation | < 12.0 | > 28.0 | MJ/m²/d |
| wind_speed | — | > 40.0 | km/h |
| evapotranspiration | — | > 9.0 | mm/d |

### Palma de aceite (`oil_palm`)

| Variable | Alerta baja | Alerta alta | Unidad |
|----------|-------------|-------------|--------|
| temperature_air | < 18.0 | > 38.0 | °C |
| humidity | < 60.0 | — | % |
| soil_ph | < 4.0 | > 7.0 | pH |
| wind_speed | — | > 25.2 | km/h |

---

## 8. Infraestructura Docker

El `docker-compose.yml` levanta 5 servicios:

```
┌─────────────┬──────────────────────────┬────────┬─────────────────────────────┐
│ Servicio    │ Imagen                   │ Puerto │ Depende de                  │
├─────────────┼──────────────────────────┼────────┼─────────────────────────────┤
│ mosquitto   │ eclipse-mosquitto:latest │ 1883   │ —                           │
│ simulator   │ build: ../fase_2         │ —      │ mosquitto (healthy)         │
│ influxdb    │ influxdb:2.7             │ 8086   │ —                           │
│ gateway     │ build: .                 │ —      │ influxdb + mosquitto (healthy)│
│ grafana     │ grafana/grafana:latest   │ 3000   │ influxdb (healthy)          │
└─────────────┴──────────────────────────┴────────┴─────────────────────────────┘
```

Todos los servicios tienen `restart: unless-stopped`. InfluxDB y Mosquitto tienen healthchecks; el gateway y Grafana esperan a que estén listos antes de arrancar.

**Volúmenes persistentes:**

| Volumen | Servicio | Propósito |
|---------|----------|-----------|
| `influxdb_data` | influxdb | Datos de series temporales |
| `influxdb_config` | influxdb | Configuración de InfluxDB |
| `mosquitto_data` | mosquitto | Mensajes persistentes |
| `mosquitto_log` | mosquitto | Logs del broker |
| `grafana_data` | grafana | Dashboards y configuración local |

---

## 9. Cómo ejecutarlo

### Requisitos previos

- Docker >= 24 y Docker Compose v2
- Los datasets en `../datasets/` (relativo a `gateway_iot/`):
  - `sugarcane-prediction-dataset.csv`
  - `crop-production-countries.csv`

Verificar que los datasets existen:

```bash
ls ../datasets/
```

### Primer arranque

```bash
cd gateway_iot
docker compose up --build
```

El flag `--build` construye las imágenes del gateway y del simulador. En arranques posteriores se puede omitir:

```bash
docker compose up
```

### Arranque en segundo plano

```bash
docker compose up --build -d
docker compose logs -f gateway    # ver logs del gateway en tiempo real
```

### Detener el stack

```bash
docker compose down               # detiene y elimina contenedores
docker compose down -v            # también elimina volúmenes (borra todos los datos)
```

### Reconstruir solo el gateway (tras cambios en el código)

```bash
docker compose up --build gateway
```

---

## 10. Verificación end-to-end

### 1. Logs del gateway

Deben aparecer líneas como estas desde los primeros 30 segundos:

```
[pipeline] parcela_1 | sugarcane | quality_score=0.92 | heat_stress=0 | water_stress=0 | alerts=0
[alert] parcela_3 | oil_palm | humidity=52.3 < 60.0 → WARNING
[pipeline] parcela_3 | oil_palm | quality_score=1.00 | heat_stress=0 | water_stress=0 | alerts=1
```

```bash
docker compose logs -f gateway
```

### 2. Datos crudos en InfluxDB

1. Abrir `http://localhost:8086`
2. Usuario: `admin` / Contraseña: `agro_admin_2026`
3. Data Explorer → bucket `agro_iot_data` → measurement `sensor_data`

### 3. Datos procesados

Data Explorer → bucket `agro_iot_processed`  
Buscar los campos: `heat_stress_index`, `water_stress_flag`, `quality_score`

### 4. Alertas

Data Explorer → bucket `agro_iot_alerts` → measurement `alert_events`  
Tags disponibles: `parcela`, `cultivo`, `variable`, `severity`, `threshold_type`

### 5. Buckets creados automáticamente

```bash
docker compose exec influxdb influx bucket list --org agricultura \
  --token agro-iot-token-fase3-icesi-2026
```

Deben aparecer los tres: `agro_iot_data`, `agro_iot_processed`, `agro_iot_alerts`.

### 6. Dashboard Grafana

Abrir `http://localhost:3000`  
Usuario: `admin` / Contraseña: `agro_grafana_2026`

El dashboard "Monitoreo Agroclimático IoT" aparece en la carpeta **IoT Agricola** sin ninguna configuración adicional. El datasource `InfluxDB-Processed` debe mostrar estado **Connected** en Settings → Data Sources.

---

## 11. Dashboard Grafana

El dashboard `agro_dashboard.json` está pre-provisionado con 13 paneles organizados en 4 filas:

### Fila 1 — Estado actual (Stat panels)

Muestran el **último valor** conocido con código de color por umbral:

- Temperatura actual — parcela_1, parcela_2, parcela_3, parcela_4 (4 paneles independientes)
- Humedad del suelo actual — parcela_1 y parcela_3 combinadas (1 panel)

### Fila 2 — Series de tiempo (últimas 6 horas)

- `temperature_air` — las 4 parcelas superpuestas
- `humidity` — las 4 parcelas
- `soil_moisture` — parcela_1 y parcela_3

### Fila 3 — Series de tiempo

- `rainfall` — las 4 parcelas
- `soil_ph` — parcela_1 y parcela_3
- `solar_radiation` — parcela_1, parcela_2, parcela_3

### Fila 4 — Indicadores de estrés (Bar Gauge)

- `heat_stress_index` por parcela — verde (0) / rojo (1)
- `water_stress_flag` por parcela — verde (0) / rojo (1)
- `quality_score` por parcela — rojo < 0.5 / amarillo < 0.9 / verde ≥ 0.9

### Anotaciones de alerta

Grafana consulta el bucket `agro_iot_alerts` y pinta líneas verticales rojas en todos los paneles de tiempo cada vez que hay un evento de alerta. El tooltip muestra parcela y variable afectada.

El dashboard se refresca automáticamente cada **30 segundos**.

---

## 12. Configurar alertas por correo

Las alertas de Grafana pueden enviarse por email vía Gmail SMTP.

### Paso 1 — Generar App Password de Gmail

1. Ir a [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Activar **Verificación en 2 pasos** (si no está activa)
3. Buscar **Contraseñas de aplicaciones**
4. Generar una contraseña para "Correo" → copiar la contraseña de 16 caracteres

### Paso 2 — Editar `grafana/grafana.ini`

```ini
[smtp]
enabled = true
host = smtp.gmail.com:587
user = tu_correo@gmail.com           # ← reemplazar
password = abcd efgh ijkl mnop       # ← App Password de 16 caracteres
from_address = tu_correo@gmail.com   # ← reemplazar
from_name = Sistema IoT Agricola
skip_verify = true
```

### Paso 3 — Reiniciar Grafana

```bash
docker compose restart grafana
```

### Paso 4 — Crear alert rule en Grafana

1. Ir a `http://localhost:3000` → **Alerting** → **Alert rules** → **New alert rule**
2. Seleccionar datasource `InfluxDB-Processed`
3. Usar una query Flux como condición, por ejemplo temperatura alta:

```flux
from(bucket: "agro_iot_processed")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "temperature_air")
  |> mean()
```

4. Configurar condición: `IS ABOVE 38`
5. Agregar **Contact point** de tipo Email con tu dirección
6. Guardar la regla

---

## 13. Variables de entorno

Todas las variables tienen valores por defecto funcionales. Copiar `.env.example` para personalizarlas:

```bash
cp .env.example .env
```

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MQTT_BROKER` | `mosquitto` | Hostname del broker MQTT |
| `MQTT_PORT` | `1883` | Puerto MQTT |
| `MQTT_TOPIC` | `agricultura/sensores/#` | Topic de suscripción |
| `INFLUX_URL` | `http://influxdb:8086` | URL de InfluxDB |
| `INFLUX_TOKEN` | `agro-iot-token-fase3-icesi-2026` | Token de autenticación |
| `INFLUX_ORG` | `agricultura` | Organización en InfluxDB |
| `INFLUX_BUCKET_RAW` | `agro_iot_data` | Bucket de datos crudos |
| `INFLUX_BUCKET_PROCESSED` | `agro_iot_processed` | Bucket de datos procesados |
| `INFLUX_BUCKET_ALERTS` | `agro_iot_alerts` | Bucket de alertas |
| `GF_SECURITY_ADMIN_USER` | `admin` | Usuario admin de Grafana |
| `GF_SECURITY_ADMIN_PASSWORD` | `agro_grafana_2026` | Contraseña admin de Grafana |

---

## 14. Troubleshooting

### El gateway no arranca — "broker no disponible"

El gateway reintenta la conexión MQTT hasta 15 veces con 3 segundos de pausa. Si Mosquitto tarda en iniciar, el gateway espera automáticamente. Si persiste:

```bash
docker compose logs mosquitto
docker compose restart gateway
```

### InfluxDB no responde

Verificar que el healthcheck pase antes de que el gateway intente conectarse:

```bash
docker compose ps influxdb    # debe mostrar "healthy"
docker compose logs influxdb
```

### No aparecen datos en Grafana

1. Verificar que el gateway esté procesando mensajes: `docker compose logs gateway`
2. Verificar que el datasource esté conectado: Grafana → Settings → Data Sources → `InfluxDB-Processed` → Test
3. Ampliar el rango de tiempo del dashboard a "Last 1 hour" o "Last 6 hours"

### El bucket `agro_iot_processed` no existe

El gateway lo crea al arrancar. Si hay un error de permisos, verificar que el token tenga acceso de escritura:

```bash
docker compose logs gateway | grep -i bucket
```

### Error de JSON en los logs

```
JSON inválido en topic '...'
```

Indica que el simulador envió un mensaje malformado. Es un aviso no crítico; el pipeline descarta ese mensaje y continúa.

### Reiniciar todo desde cero (borrar datos)

```bash
docker compose down -v
docker compose up --build
```

---

## Referencia rápida de comandos

```bash
# Arrancar
docker compose up --build

# Ver logs en tiempo real
docker compose logs -f gateway
docker compose logs -f grafana

# Estado de los servicios
docker compose ps

# Reiniciar un servicio
docker compose restart gateway

# Detener (conserva datos)
docker compose down

# Detener y borrar todo
docker compose down -v

# Accesos
# Grafana:  http://localhost:3000  (admin / agro_grafana_2026)
# InfluxDB: http://localhost:8086  (admin / agro_admin_2026)
# MQTT:     localhost:1883
```
