# Sistema de Monitoreo de Sensores IoT y Analítica Agroclimática

**Universidad ICESI · Departamento de Computación y Sistemas Inteligentes**
**Sistemas y Comunicaciones I · Prof. Gonzalo Llano R. · Mayo 2026**

Sistema IoT completo para monitorear variables agroclimáticas en parcelas de **caña de azúcar** y **palma de aceite** en el contexto del **Valle del Cauca, Colombia**. Usa sensores simulados a partir de datasets reales, broker MQTT, base de datos de series temporales, pipeline de procesamiento con cálculo de indicadores agronómicos avanzados (VPD, ETo FAO, GDD, riesgo de enfermedad, balance hídrico) y dashboard interactivo Grafana.

---

## Lo que se ejecuta y se presenta

El proyecto se presenta levantando un único stack: `gateway_iot/`. Las carpetas `fase_1/`, `fase_2/` y `fase_3/` documentan la evolución incremental del proyecto durante el curso, pero **el ejecutable final es `gateway_iot/`**, que incluye internamente el simulador (importado desde `fase_2/`), el gateway IoT, InfluxDB y Grafana.

```bash
cd gateway_iot
docker compose up --build
```

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Grafana — dashboard** | http://localhost:3000 | admin / agro_grafana_2026 |
| **InfluxDB** | http://localhost:8086 | admin / agro_admin_2026 |
| MQTT Broker | localhost:1883 | sin autenticación |

El dashboard **"Monitoreo Agroclimático IoT — Sistema Integral"** aparece automáticamente en la carpeta **IoT Agricola** sin configuración adicional.

> Para la guía paso-a-paso de ejecución y captura de evidencias por fase, ver **[`GUIA_PRESENTACION.md`](./GUIA_PRESENTACION.md)**.

---

## Resumen por fase

### Fase 1 — Exploración del dataset agroclimático *(ya revisada por el profesor)*

Análisis EDA en `fase_1/eda_agroclimatico.ipynb` sobre 3 datasets:

| Dataset | Registros | Uso |
|---------|-----------|-----|
| `sugarcane-prediction-dataset.csv` | 3.000 (81 variables) | Caña de azúcar — datos reales de campo |
| `crop-production-countries.csv` | 24.500 (375 de palma) | Palma de aceite — datos globales por país-año |
| `sugarcane-dataset-2.csv` | 90 | Validación cruzada |

Random Forest alcanza R²=0.766 explicando rendimiento. Identifica `Nitrogen` (r=+0.46), `Soil_Moisture` (Δ+13.2% Q4 vs Q1) y `Temp_Avg` como variables más impactantes. Define los **rangos validados para Valle del Cauca** (caña 20–30°C, palma 24–32°C) que alimentan los umbrales de las fases 4/5.

### Fase 2 — Simulador de sensores IoT (4 parcelas, MQTT)

`fase_2/simulator.py` — simulador multi-thread Python que **se ejecuta como contenedor dentro del stack `gateway_iot/`**.

| Parcela | Cultivo | Área | Sensores simulados |
|---------|---------|------|--------------------|
| parcela_1 | sugarcane | 5.0 ha | temp, HR, lluvia, pH, soil_moisture, radiación |
| parcela_2 | sugarcane | 3.5 ha | temp, HR, lluvia, viento |
| parcela_3 | oil_palm | 8.0 ha | temp, HR, lluvia, pH, soil_moisture, radiación |
| parcela_4 | oil_palm | 6.5 ha | temp, HR, lluvia, viento |

**Configuración heterogénea deliberada:** parcelas con diferentes pliegues de sensores instalados — refleja un escenario real donde no todas las parcelas tienen la misma infraestructura.

**¿Qué alimenta a cada cultivo?**

- **Caña:** todas las variables se leen de `sugarcane-prediction-dataset.csv` (datos reales de campo).
- **Palma:** `temperature_air` y `rainfall` se leen de `crop-production-countries.csv` (datos reales por país); la lluvia anual se divide entre 12 para obtener una tasa mensual coherente con el dataset de caña. Las demás variables (`humidity`, `soil_ph`, `soil_moisture`, `solar_radiation`, `wind_speed`) se generan con un **proceso AR(1)** sobre distribuciones derivadas del EDA §7.2 (medias, desviaciones, rangos), produciendo series temporales suaves y realistas.

**Frecuencias de envío** comprimidas para visualización (en sistema real serían 15 min – 2 h):
temperatura/HR/viento cada 15 s · soil_moisture/radiación cada 30 s · lluvia/pH cada 60 s.

**Ruido gaussiano** calibrado a specs reales de hardware (DHT22 ±0.5°C, capacitivo de suelo ±0.5%, etc.).

**Rangos clip post-ruido ajustados al Valle del Cauca**: caña 20–33°C, palma 22–33°C — coherentes con la media regional de 27.1°C reportada en el EDA §11.

**Evapotranspiración:** *no* se simula como sensor. Se calcula en el gateway (FAO Jensen-Haise) — ver Fase 4.

**Payload MQTT** publicado a `agricultura/sensores/<parcela>` con QoS=1:
```json
{ "timestamp": "2026-05-23 14:32:01", "parcela": "parcela_1",
  "cultivo": "sugarcane", "area_ha": 5.0,
  "temperature_air": 27.8, "humidity": 72.3, "rainfall": 1450.0,
  "soil_ph": 6.8, "soil_moisture": 26.5, "solar_radiation": 22.4 }
```

### Fase 3 — Ingestión y almacenamiento de datos crudos

`gateway_iot/core/mqtt_client.py` se suscribe a `agricultura/sensores/#`, recibe los mensajes y `gateway_iot/core/influx_writer.py` los persiste **tal como llegan** en el bucket `agro_iot_data` de InfluxDB con tags `parcela`, `cultivo`, `area_ha`.

**Decisión técnica — Python en lugar de Node-RED:** el PDF sugiere Node-RED para esta fase pero se reemplaza por Python porque:
1. permite testing unitario y tipado con dataclasses,
2. soporta cálculos agronómicos no triviales (VPD, ETo Penman-Monteith, GDD) imposibles en nodos de Node-RED sin código embebido,
3. arquitectura desacoplada con SRP (`DataValidator`, `DataEnricher`, `AlertChecker`, `InfluxWriter`) — cada componente es testeable y reemplazable.
El gateway implementa el mismo modelo Publisher/Subscribe + flow `MQTT→parse→transform→store` que se haría en Node-RED.

### Fase 4 — Procesamiento de datos: cálculo de 11 variables agronómicas derivadas

Este es el "cerebro" del sistema. Cada lectura validada se enriquece con indicadores agronómicos basados en literatura estándar (FAO-56, Tetens, NRC-1971):

| Derivada | Fórmula | Uso operacional |
|----------|---------|-----------------|
| **VPD** (kPa) | Tetens | Indicador #1 de estrés foliar — >3 kPa cierra estomas |
| **dew point** (°C) | Magnus | Predice condensación → enfermedades fúngicas |
| **THI** | NRC 1971 | Bochorno integrado T+HR |
| **heat_index** (0–1) | tanh ponderado por HR | Reemplazo continuo del flag binario |
| **ETo** (mm/d) | FAO Jensen-Haise | Evapotranspiración de referencia |
| **ETc** (mm/d) | ETo·Kc | Requerimiento hídrico del cultivo |
| **water_balance** (mm/d) | (lluvia/30) − ETc | Negativo = déficit, hay que regar |
| **gdd_increment** | max(0, T−Tbase) | Grados-día térmicos, fenología |
| **disease_risk** (0–1) | Lógica por cultivo | Roya/mancha (caña) · pudrición cogollo (palma) |
| **irrigation_need** (0–1) | f(soil_moisture, balance) | Recomendación accionable de riego |
| **quality_score** (0–1) | válidos / (válidos+inválidos) | Calidad del payload |

Las constantes por cultivo (Tbase, Kc, Topt) están en `config/thresholds.py`. Los datos validados + las 11 derivadas se persisten en el bucket `agro_iot_processed`.

### Fase 5 — Umbrales agronómicos y generación de alertas

- **Umbrales** definidos en `config/thresholds.py` y validados con el EDA §7.1 (caña) y §7.2 (palma), con rangos ajustados al Valle del Cauca.
- **AlertChecker** evalúa 11 variables (crudas + derivadas) contra los umbrales por cultivo.
- **Clasificación de severidad:** `warning` (exceso ≤ 20%) o `critical` (exceso > 20%).
- **Persistencia:** eventos escritos en el bucket `agro_iot_alerts` (measurement `alert_events`) con tags `parcela`, `cultivo`, `variable`, `severity`, `threshold_type`.
- **Notificaciones:** Grafana lee este bucket y dispara alertas por SMTP/Gmail (ver `gateway/grafana/grafana.ini` y `grafana/provisioning/alerting/`).
- **Reglas pre-provisionadas:** 10 reglas en 4 grupos (estrés calórico, hídrico, temp. extrema, HR baja palma/caña, viento palma, VPD, riesgo enfermedad, riego, calidad de datos).
- **Generador de eventos de prueba:** `gateway_iot/alert_creator.py` publica payloads extremos por MQTT para validar cada regla (escenarios heat / water / wind / humidity / vpd / disease / irrigation / quality).

### Fase 6 — Machine Learning *(implementada por un compañero)*

### Fase 7 — Visualización y dashboard integrado

Dashboard Grafana **"Monitoreo Agroclimático IoT — Sistema Integral"** con **27 paneles en 6 filas** y **2 variables de template interactivas** (`$parcela`, `$cultivo`):

1. **Resumen ejecutivo** (6 stats): alertas activas, críticas 24h, mensajes/min, quality, VPD máx, ETo
2. **Estado por parcela** (4 tarjetas multi-variable)
3. **Variables primarias** (4 timeseries): temperatura, HR, suelo, lluvia
4. **Variables secundarias** (3 timeseries): viento, radiación, pH
5. **Derivadas agronómicas** (6 timeseries): VPD, ETo+ETc, GDD, riesgo enfermedad, heat index, balance hídrico
6. **Riesgo y calidad** (4 bargauge): riego, enfermedad, estrés hídrico, quality
7. **Alertas** (tabla + pie chart): últimas 30 alertas + conteo por severidad

Refresh automático cada 30 s. Anotaciones de alertas pintadas como líneas verticales en todos los paneles temporales.

---

## Arquitectura del sistema

```
┌──────────────────────────────────────────────────────────────────┐
│  Simulador (Fase 2) — 4 parcelas en hilos paralelos              │
│  Caña: sugarcane-prediction-dataset.csv (variables reales)       │
│  Palma: crop-production-countries.csv + AR(1) sobre EDA §7.2     │
└────────────────────┬─────────────────────────────────────────────┘
                     │ MQTT  agricultura/sensores/<parcela>  QoS=1
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Eclipse Mosquitto :1883                                          │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Gateway IoT (Python) — gateway_iot/                              │
│  MQTTClient → DataPipeline:                                       │
│    Validator → Enricher (11 derivadas) → AlertChecker → Writer   │
└──────┬───────────────────────────────────────────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  InfluxDB :8086                                                   │
│  ├── agro_iot_data       (7 variables crudas)                    │
│  ├── agro_iot_processed  (7 crudas + 11 derivadas + flags + QS)  │
│  └── agro_iot_alerts     (eventos warning/critical, 30d retención)│
└──────────────────────┬───────────────────────────────────────────┘
                       │ Flux queries
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Grafana :3000  — Dashboard "Monitoreo Agroclimático IoT"        │
│  27 paneles · Templates parcela/cultivo · Anotaciones · Alerts   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Estructura del proyecto

```
proyecto_final/
├── datasets/                        # Datasets agroclimáticos públicos
│   ├── sugarcane-prediction-dataset.csv   → Caña (Fase 2 — todas las variables)
│   ├── crop-production-countries.csv      → Palma (Fase 2 — T y lluvia reales)
│   └── sugarcane-dataset-2.csv            → Validación cruzada (Fase 1)
│
├── fase_1/                          # EDA — ya revisado por el profesor
├── fase_2/
│   └── simulator.py                 # Simulador (se ejecuta dentro de gateway_iot)
├── fase_3/                          # Gateway monolítico inicial (referencia histórica)
│
├── gateway_iot/                     # ★ PROYECTO QUE SE PRESENTA ★
│   ├── main.py                      # Entry point
│   ├── docker-compose.yml           # Stack completo: 5 servicios
│   ├── config/
│   │   ├── settings.py
│   │   └── thresholds.py            # Umbrales + constantes Tbase/Kc/Topt por cultivo
│   ├── models/
│   │   └── sensor_reading.py        # SensorReading con 11 campos derivados
│   ├── core/
│   │   ├── mqtt_client.py
│   │   ├── influx_writer.py         # Escribe a 3 buckets
│   │   └── pipeline.py
│   ├── processors/
│   │   ├── validator.py             # Rangos físicos
│   │   ├── agronomic.py             # Fórmulas FAO/Tetens/Magnus
│   │   ├── enricher.py              # Llama agronomic.py
│   │   └── alert_checker.py         # Umbrales para 11 variables
│   ├── grafana/
│   │   ├── grafana.ini
│   │   └── provisioning/
│   │       ├── datasources/influxdb.yaml
│   │       ├── dashboards/agro_dashboard.json     # 27 paneles
│   │       └── alerting/                          # 10 reglas + contact points
│   ├── alert_creator.py             # Generador de eventos extremos para probar alertas
│   └── README.md                    # Documentación técnica detallada del gateway
│
├── README.md                        # Este archivo
├── GUIA_PRESENTACION.md             # Guía paso-a-paso ejecución y capturas
└── trabajo-final.pdf                # Enunciado del trabajo
```

---

## Datasets — quién alimenta qué

| Dataset | Cultivo | Variables que aporta | Fase que lo usa |
|---------|---------|---------------------|-----------------|
| `sugarcane-prediction-dataset.csv` | Caña | T, HR, lluvia, pH, soil_moisture, radiación, viento | Fase 1 (EDA), Fase 2 (simulador parcelas 1–2) |
| `crop-production-countries.csv` (filas con `palm`) | Palma | T media anual, lluvia anual (÷12) | Fase 2 (simulador parcelas 3–4, sólo T y lluvia) |
| EDA §7.2 — distribuciones (mean, std, lo, hi) | Palma | HR, pH, soil_moisture, radiación, viento — vía AR(1) | Fase 2 (simulador parcelas 3–4, resto de sensores) |
| `sugarcane-dataset-2.csv` | Caña | T, lluvia, NPK, rendimiento (referencia) | Fase 1 (validación cruzada) |

---

## Próximos pasos para la presentación

Ver **[`GUIA_PRESENTACION.md`](./GUIA_PRESENTACION.md)** para:
- Pre-requisitos del entorno
- Secuencia de comandos para arrancar
- Qué capturar en cada fase
- Cómo disparar las alertas para mostrarlas funcionando
- Tips y respuestas a las dudas más probables del profesor
