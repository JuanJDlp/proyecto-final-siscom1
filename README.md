# Sistema de Monitoreo de Sensores IoT y Analítica Agroclimática

**Universidad ICESI · Departamento de Computación y Sistemas Inteligentes**  
**Sistemas y Comunicaciones I · Prof. Gonzalo Llano R. · Mayo 2026**

Sistema IoT completo para monitorear variables agroclimáticas en parcelas de caña de azúcar y palma de aceite, usando sensores simulados, MQTT, InfluxDB y Grafana.

---

## Estructura del proyecto

```
proyecto_final/
│
├── datasets/                        # Datasets agroclimáticos públicos
│   ├── sugarcane-prediction-dataset.csv   # Caña de azúcar (3.000 filas, 81 variables)
│   ├── crop-production-countries.csv      # Palma de aceite (producción global)
│   └── sugarcane-dataset-2.csv            # Dataset simplificado (referencia)
│
├── fase_1/                          # EDA del dataset agroclimático
│   ├── eda_agroclimatico.ipynb      # Notebook Jupyter (78 celdas, análisis completo)
│   ├── analisis_eda.md              # Resumen ejecutivo con umbrales y hallazgos
│   └── *.png                        # 13 visualizaciones exportadas
│
├── fase_2/                          # Simulador de sensores IoT
│   ├── simulator.py                 # Simulador Python (4 parcelas, MQTT)
│   ├── docker-compose.yml           # Mosquitto + Simulador
│   ├── Dockerfile
│   └── README.md
│
├── fase_3/                          # Gateway IoT monolítico (ingestión en InfluxDB)
│   ├── gateway/
│   │   └── gateway.py               # Gateway Python: MQTT → InfluxDB
│   ├── docker-compose.yml           # Mosquitto + Simulador + InfluxDB + Gateway
│   ├── mosquitto/mosquitto.conf
│   └── README.md
│
├── gateway_iot/                     # Gateway refactorizado + Pipeline + Grafana
│   ├── main.py                      # Entry point
│   ├── docker-compose.yml           # Stack completo (5 servicios)
│   ├── config/                      # Settings + umbrales agroclimáticos
│   ├── models/                      # Dataclasses SensorReading y AlertEvent
│   ├── core/                        # Pipeline, InfluxWriter, MQTTClient
│   ├── processors/                  # Validator, Enricher, AlertChecker
│   ├── grafana/                     # Dashboard + datasources pre-configurados
│   └── README.md                    # Documentación completa
│
├── trabajo-final.pdf                # Enunciado del trabajo
└── informe_completitud.md           # Análisis de completitud vs. rúbrica
```

---

## Fases implementadas

| Fase | Descripción | Ubicación | Estado |
|------|-------------|-----------|--------|
| **Fase 1** | EDA del dataset agroclimático | `fase_1/` | ✅ Completo |
| **Fase 2** | Simulador de sensores IoT (4 parcelas, MQTT) | `fase_2/` | ✅ Completo |
| **Fase 3** | Gateway de ingestión → InfluxDB | `fase_3/` | ✅ Completo |
| **Fase 4** | Pipeline de procesamiento en tiempo real | `gateway_iot/` | ✅ Completo |
| **Fase 5** | Umbrales agroclimáticos y generación de alertas | `gateway_iot/` | ✅ Completo |
| **Fase 7** | Dashboard Grafana pre-provisionado | `gateway_iot/` | ✅ Completo |

---

## Inicio rápido — Stack completo (Fases 4, 5 y 7)

> Prerequisitos: Docker >= 24 y Docker Compose v2.

```bash
cd gateway_iot
docker compose up --build
```

Accesos tras el arranque:

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| Grafana (dashboard) | http://localhost:3000 | admin / agro_grafana_2026 |
| InfluxDB | http://localhost:8086 | admin / agro_admin_2026 |
| MQTT Broker | localhost:1883 | sin autenticación |

El dashboard **"Monitoreo Agroclimático IoT"** aparece automáticamente en la carpeta **IoT Agricola** sin configuración adicional.

---

## Arquitectura del sistema

```
┌──────────────────────────────────────────────────────────────────┐
│  Fase 2 — Simulador                                              │
│  4 parcelas · 2 cultivos · datasets reales CSV · ruido gaussiano │
└────────────────────┬─────────────────────────────────────────────┘
                     │ MQTT  agricultura/sensores/<parcela>
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Eclipse Mosquitto :1883  (Broker MQTT)                          │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Gateway IoT Python (Fase 3 / gateway_iot)                       │
│  Validate → Enrich → AlertCheck → Write                          │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  InfluxDB :8086                                                   │
│  ├── agro_iot_data       (datos crudos)                          │
│  ├── agro_iot_processed  (datos + heat_stress, water_stress, QS) │
│  └── agro_iot_alerts     (eventos de alerta warning/critical)    │
└──────────────────────┬───────────────────────────────────────────┘
                       │ Flux queries
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Grafana :3000  — Dashboard "Monitoreo Agroclimático IoT"        │
│  13 paneles · Stat · TimeSeries · BarGauge · Anotaciones         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Parcelas simuladas

| Parcela | Cultivo | Área | Sensores |
|---------|---------|------|----------|
| parcela_1 | Caña de azúcar | 5.0 ha | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_2 | Caña de azúcar | 3.5 ha | temperature_air, humidity, rainfall, wind_speed, evapotranspiration |
| parcela_3 | Palma de aceite | 8.0 ha | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_4 | Palma de aceite | 6.5 ha | temperature_air, humidity, rainfall, wind_speed |

---

## Ejecutar por fase individual

### Fase 1 — EDA

```bash
cd fase_1
jupyter notebook eda_agroclimatico.ipynb
```

### Fase 2 — Simulador solo

```bash
cd fase_2
docker compose up --build
# Mensajes MQTT visibles en los logs del contenedor iot_simulator
```

### Fase 3 — Gateway monolítico

```bash
cd fase_3
docker compose up --build
# Gateway escribe en InfluxDB: http://localhost:8086
```

### Fases 4 + 5 + 7 — Stack completo

```bash
cd gateway_iot
docker compose up --build
```

---

## Datasets utilizados

| Dataset | Registros | Variables clave | Uso |
|---------|-----------|-----------------|-----|
| `sugarcane-prediction-dataset.csv` | 3.000 | Temp, Humedad, Lluvia, pH, Soil Moisture, Radiación, Viento, ET | Caña de azúcar (Fases 1, 2) |
| `crop-production-countries.csv` | 375 (palma) | Temperatura media, Lluvia anual | Palma de aceite (Fase 2) |
| `sugarcane-dataset-2.csv` | — | Referencia EDA | Fase 1 |
