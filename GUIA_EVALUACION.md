# Guía de Evaluación — Sistema IoT Agroclimático

**Universidad ICESI · Sistemas y Comunicaciones I · Prof. Gonzalo Llano R.**

Esta guía describe paso a paso cómo arrancar el sistema y qué verificar en cada fase, alineado con los criterios de la rúbrica de evaluación.

---

## Requisitos previos

| Requisito | Versión mínima | Verificar |
|---|---|---|
| Docker Engine | 24+ | `docker --version` |
| Docker Compose v2 | 2.x | `docker compose version` |
| Espacio en disco | ~3 GB (imágenes + datos) | — |

Los datasets deben estar en `datasets/` (relativo a la raíz del proyecto):

```
datasets/
├── sugarcane-prediction-dataset.csv
└── crop-production-countries.csv
```

---

## Arrancar el sistema

Todo el stack se levanta con **un solo comando** desde la carpeta `gateway_iot/`:

```bash
cd gateway_iot
docker compose up --build
```

El flag `--build` construye las imágenes del gateway, el simulador y el servicio ML. En arranques posteriores se puede omitir:

```bash
docker compose up
```

**Tiempo hasta estado operativo:** ~90 segundos desde que todos los contenedores arrancan.

### Servicios que se levantan

| Servicio | Descripción | Puerto |
|---|---|---|
| `mosquitto` | Broker MQTT | 1883 |
| `simulator` | Simulador de 4 parcelas agrícolas | — |
| `influxdb` | Base de datos de series temporales | 8086 |
| `gateway` | Pipeline IoT: validación, enriquecimiento, alertas | — |
| `ml_service` | Servicio de predicción Machine Learning | — |
| `grafana` | Dashboard de visualización | 3000 |

### Accesos

| Servicio | URL | Usuario | Contraseña |
|---|---|---|---|
| Grafana | http://localhost:3000 | admin | agro_grafana_2026 |
| InfluxDB | http://localhost:8086 | admin | agro_admin_2026 |
| MQTT | localhost:1883 | — | — |

---

## Verificación por fase (rúbrica)

### Fase 1 — Preparación del entorno y análisis exploratorio

**Criterio:** Instalación de herramientas y generación de datos a partir del dataset agroclimático.

**Evidencia — Jupyter Notebook EDA:**

Abrir `fase_1/eda_agroclimatico.ipynb`. El notebook ya ejecutado contiene:
- Análisis de 3 datasets (81 variables, 3.000 registros de caña; 24.500 globales de palma).
- Correlaciones, distribuciones, boxplots y series mensuales.
- Random Forest que alcanza R²=0.766 para predecir rendimiento.
- Definición de rangos óptimos para el Valle del Cauca (usados como umbrales en Fase 5).

Las imágenes generadas se encuentran en `fase_1/*.png`.

---

### Fase 2 — Simulación de sensores IoT (4 parcelas, MQTT)

**Criterio:** Simulador genera datos reales del dataset en las 4 parcelas. Datos publicados correctamente en topics MQTT.

**Evidencia — Ver logs del simulador:**

```bash
docker compose logs -f simulator
```

Output esperado:
```
[parcela_1] sugarcane | temperature_air=27.4 humidity=71.2 rainfall=1450.0 ...
[parcela_2] sugarcane | temperature_air=26.9 humidity=68.5 ...
[parcela_3] oil_palm  | temperature_air=28.1 humidity=82.3 ...
[parcela_4] oil_palm  | temperature_air=27.7 humidity=79.4 ...
```

Las 4 parcelas publican simultáneamente (hilos paralelos) al topic `agricultura/sensores/<parcela>`.

**Evidencia — Captura de mensajes MQTT recibidos por el gateway:**

```bash
docker compose logs -f gateway | grep "Recibido\|parcela"
```

Output esperado (primeros 30 segundos):
```
[mqtt] Recibido mensaje de parcela_1
[mqtt] Recibido mensaje de parcela_3
[mqtt] Recibido mensaje de parcela_2
```

**Detalle de las 4 parcelas:**

| Parcela | Cultivo | Área | Fuente de datos |
|---|---|---|---|
| parcela_1 | Caña de azúcar | 5.0 ha | `sugarcane-prediction-dataset.csv` — variables reales |
| parcela_2 | Caña de azúcar | 3.5 ha | `sugarcane-prediction-dataset.csv` — variables reales |
| parcela_3 | Palma de aceite | 8.0 ha | `crop-production-countries.csv` (T, lluvia) + AR(1) sobre EDA |
| parcela_4 | Palma de aceite | 6.5 ha | `crop-production-countries.csv` (T, lluvia) + AR(1) sobre EDA |

---

### Fase 3 — Ingestión de datos IoT (almacenamiento de datos crudos)

**Criterio:** Gateway recibe datos MQTT correctamente. Datos almacenados correctamente en base de datos de series temporales.

**Evidencia — Ver datos crudos en InfluxDB:**

1. Abrir http://localhost:8086
2. Usuario: `admin` / Contraseña: `agro_admin_2026`
3. Ir a **Data Explorer** → bucket `agro_iot_data` → measurement `sensor_data`
4. Seleccionar campo `temperature_air` y cualquier parcela → ejecutar query

Debe mostrar una serie temporal con lecturas cada ~15 segundos.

**Verificar que los 3 buckets existen:**

```bash
docker compose exec influxdb influx bucket list \
  --org agricultura \
  --token agro-iot-token-fase3-icesi-2026
```

Deben aparecer: `agro_iot_data`, `agro_iot_processed`, `agro_iot_alerts`.

---

### Fase 4 — Procesamiento de datos (transformación y variables derivadas)

**Criterio:** Datos procesados correctamente. Transformación y limpieza de datos.

**Evidencia — Logs del pipeline:**

```bash
docker compose logs -f gateway | grep "\[pipeline\]"
```

Output esperado:
```
[pipeline] parcela_1 | sugarcane | quality_score=0.92 | heat_stress=0 | water_stress=0 | alerts=0
[pipeline] parcela_3 | oil_palm  | quality_score=1.00 | heat_stress=0 | water_stress=0 | alerts=1
```

**Evidencia — Datos procesados en InfluxDB:**

1. Data Explorer → bucket `agro_iot_processed`
2. Buscar los campos derivados: `vpd`, `evapotranspiration`, `disease_risk`, `gdd_increment`, `water_balance`, `irrigation_need`, `quality_score`

**Las 11 variables derivadas calculadas por el gateway:**

| Variable | Fórmula | Significado |
|---|---|---|
| `vpd` | Tetens | Déficit de presión de vapor (estrés foliar) |
| `dew_point` | Magnus | Punto de rocío (riesgo fúngico) |
| `thi` | NRC 1971 | Temperature-Humidity Index |
| `heat_index` | tanh ponderado | Estrés calórico continuo |
| `evapotranspiration` | FAO Jensen-Haise | ETo de referencia (mm/día) |
| `crop_water_requirement` | ETo × Kc | Demanda hídrica del cultivo |
| `water_balance` | lluvia − ETc | Balance hídrico diario |
| `gdd_increment` | max(0, T−Tbase) | Grados-día térmicos (fenología) |
| `disease_risk` | Lógica por cultivo | Riesgo de roya/pudrición (0–1) |
| `irrigation_need` | f(soil_moisture, balance) | Recomendación de riego (0–1) |
| `quality_score` | válidos/total | Calidad del payload (0–1) |

---

### Fase 5 — Umbrales y generación de alertas

**Criterio:** Implementación de reglas de alerta completas y funcionales.

**Evidencia — Ver alertas en tiempo real:**

```bash
docker compose logs -f gateway | grep "\[alert\]"
```

Output esperado:
```
[alert] parcela_3 | oil_palm | humidity=52.3 < 60.0 → WARNING
[alert] parcela_1 | sugarcane | vpd=3.4 > 3.0 → CRITICAL
```

**Evidencia — Disparar alertas extremas con el generador de prueba:**

Abrir una segunda terminal y ejecutar (con el stack corriendo):

```bash
docker compose exec gateway python alert_creator.py --broker mosquitto
```

Esto publica payloads extremos que disparan inmediatamente alertas `CRITICAL` para cada tipo de condición (calor, sequía, viento, humedad, VPD, enfermedad, riego, calidad).

Luego verificar en InfluxDB:
- Data Explorer → bucket `agro_iot_alerts` → measurement `alert_events`
- Deben aparecer eventos con tags: `parcela`, `cultivo`, `variable`, `severity=critical|warning`

**Reglas implementadas:** temperatura extrema, sequía/exceso hídrico, HR baja (caña y palma por separado), viento excesivo en palma, VPD crítico, riesgo de enfermedad, necesidad de riego, calidad de datos.

---

### Fase 6 — Machine Learning predictivo

**Criterio:** Modelo funcional con evaluación. Implementación de modelo predictivo.

**Evidencia — Logs del servicio ML:**

```bash
docker compose logs -f ml_service
```

Output esperado (~90 s después del arranque inicial):
```
Fase 6 — Predicción de Variables Agroclimáticas
Variables: 8 | Parcelas: 4 | Horizonte: 3 pasos (~5 min)
✔ Conectado a InfluxDB (http://influxdb:8086)
Esperando datos iniciales del simulador (60s)...
Iniciando ciclo de predicción cada 30s.
Ciclo OK — 32/32 predicciones escritas — 2.3s
```

32 predicciones = 4 parcelas × 8 variables. Si el número es menor, algunas variables aún no tienen suficientes puntos (mínimo 5).

**Evidencia — Dashboard Grafana Fase 6:**

1. Abrir http://localhost:3000
2. Navegar a la sección **"Fase 6"** del dashboard
3. Cada panel muestra línea real (sólida) vs línea predicha (punteada) por variable

**Verificar bucket ML en InfluxDB:**

```bash
docker compose exec influxdb influx bucket list \
  --org agricultura \
  --token agro-iot-token-fase3-icesi-2026
```

Debe aparecer `agro_iot_ml` además de los otros tres.

**Modelo utilizado:** Regresión Ridge (α=1.0) sobre ventana deslizante de 20 valores. Features: índice lineal, índice², media móvil de 3 puntos. Horizonte: 3 pasos ≈ ~5 minutos.

---

### Fase 7 — Visualización (dashboard Grafana)

**Criterio:** Dashboard completo con múltiples variables. Pipeline completo funcionando.

**Evidencia — Dashboard principal:**

1. Abrir http://localhost:3000
2. Usuario: `admin` / Contraseña: `agro_grafana_2026`
3. El dashboard **"Monitoreo Agroclimático IoT — Sistema Integral"** aparece en la carpeta **IoT Agricola** sin configuración adicional

**El dashboard incluye 27+ paneles organizados en 7 filas:**

| Fila | Contenido |
|---|---|
| Resumen ejecutivo | Alertas activas, mensajes/min, quality score, VPD máx, ETo |
| Estado por parcela | 4 tarjetas con hasta 7 variables simultáneas |
| Variables climáticas | Temperatura, HR, suelo, lluvia — 4 parcelas superpuestas |
| Variables secundarias | Viento, radiación solar, pH de suelo |
| Indicadores agronómicos | VPD, ETo+ETc, GDD, riesgo enfermedad, heat index, balance hídrico |
| Riesgo y calidad | Bargauge: riego, enfermedad, estrés hídrico, quality |
| Alertas | Tabla últimas 30 alertas + pie chart por severidad |

**Variables de template:** filtros interactivos `$parcela` y `$cultivo` en la barra superior.

**Verificar integración completa del pipeline:**

```bash
docker compose ps
```

Todos los servicios deben mostrar estado `running` (o `Up`). El datasource `InfluxDB-Processed` debe mostrar **Connected** en Grafana → Settings → Data Sources.

---

## Resumen de accesos rápidos

| Acción | Comando / URL |
|---|---|
| Ver todos los logs | `docker compose logs -f` |
| Logs del gateway (pipeline + alertas) | `docker compose logs -f gateway` |
| Logs del simulador | `docker compose logs -f simulator` |
| Logs del ML service | `docker compose logs -f ml_service` |
| Estado de los servicios | `docker compose ps` |
| Dashboard Grafana | http://localhost:3000 (admin / agro_grafana_2026) |
| InfluxDB Data Explorer | http://localhost:8086 (admin / agro_admin_2026) |
| Disparar alertas de prueba | `docker compose exec gateway python alert_creator.py --broker mosquitto` |

---

## Limpiar después de evaluar

```bash
# Detener y eliminar contenedores (conserva volúmenes de datos)
docker compose down

# Detener y eliminar contenedores + todos los datos
docker compose down -v
```
