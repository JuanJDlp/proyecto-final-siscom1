# Fase 6 — Predicción de Variables Agroclimáticas en Tiempo Real

**Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026**

---

## Qué hace esta fase

El servicio ML predice los **valores futuros de las 8 variables agroclimáticas** que ya monitorean los sensores IoT, para cada una de las 4 parcelas. El resultado se visualiza en Grafana como una comparación directa entre la línea real (mediciones del sensor) y la línea predicha (proyección a ~5 minutos).

Esto permite detectar:
- Si una variable está **tendiendo a salir de su rango normal** antes de que ocurra
- Si el comportamiento actual del sensor es **consistente con su tendencia reciente** o hay una anomalía

---

## Variables que se predicen

| Variable IoT | Unidad | Relevancia agronómica |
|---|---|---|
| `temperature_air` | °C | Determina la tasa de fotosíntesis y riesgo de estrés calórico |
| `humidity` | % | Afecta la transpiración y riesgo de enfermedades fúngicas |
| `rainfall` | mm | Principal fuente de agua; exceso causa anegamiento |
| `soil_ph` | pH | Controla la absorción de nutrientes; rango óptimo caña: 6.0–7.5 |
| `soil_moisture` | % | Indicador directo de estrés hídrico |
| `solar_radiation` | MJ/m²/d | Energía disponible para crecimiento |
| `wind_speed` | km/h | Afecta evapotranspiración y riesgo de volcamiento |
| `evapotranspiration` | mm/día | Balance hídrico del cultivo |

---

## Cómo funciona el modelo

### Tipo de modelo: Regresión Ridge sobre ventana deslizante

Cada 30 segundos, para cada combinación (parcela × variable):

```
Últimos 20 valores reales (ventana de ~30 min)
        │
        ▼
Construcción de features temporales:
  - t        → índice lineal (captura tendencia)
  - t²       → curvatura suave
  - media_3  → media móvil de 3 puntos (reduce ruido del sensor)
        │
        ▼
Ridge(alpha=1.0).fit(X, y)   ← regularización L2 evita sobreajuste
        │
        ▼
Proyección: 3 pasos adelante
  (cada paso ≈ intervalo promedio entre lecturas del sensor)
  → ~5 minutos de horizonte con sensores cada ~90s
        │
        ▼
Clamping a ±3σ del histórico
  (evita predicciones absurdas por ruido extremo del sensor)
```

### ¿Por qué Ridge y no ARIMA o LSTM?

| Modelo | Problema en este contexto |
|---|---|
| ARIMA | Requiere estacionariedad + ajuste de parámetros (p,d,q) por variable. Con ventanas cortas y datos ruidosos es inestable |
| LSTM | Necesita miles de puntos de entrenamiento. Con 20 puntos sobreajusta completamente |
| **Ridge** | Funciona bien con pocos puntos, es robusto al ruido, predice en microsegundos, no requiere ajuste manual |

### Horizonte de predicción: ~5 minutos

Se eligieron **3 pasos adelante** como criterio realista porque:
- Con ventanas de 20–30 min de histórico, la señal útil del modelo se agota rápido
- En sistemas IoT agrícolas, las alertas tempranas de 5–10 min son accionables (se puede activar riego, ventilación, etc.)
- Más allá de 10 min con este modelo, el error crece por encima de la variabilidad natural de los sensores

---

## Resultados en Grafana

Cada panel de la sección **"Fase 6"** muestra:
- **Línea sólida** → valor real medido por el sensor (fuente: `agro_iot_processed`)
- **Línea punteada** → valor predicho por el modelo (fuente: `agro_iot_ml`)
- Los colores identifican las 4 parcelas consistentemente con el resto del dashboard

**Interpretación:**
- Líneas real y predicha **muy juntas** → el modelo captura bien la dinámica actual
- Línea predicha **diverge hacia arriba/abajo** → la variable tiene una tendencia clara en los próximos minutos
- Línea predicha **constante cuando la real varía bruscamente** → posible anomalía del sensor (el modelo no anticipa saltos bruscos no tendenciales)

---

## Arquitectura del servicio

```
agro_iot_processed (InfluxDB)
         │  Flux query — últimos 20 valores por (parcela, variable)
         ▼
┌────────────────────────────────┐
│  ml_service  (Fase 6)          │
│  Loop cada 30s:                │
│  for parcela in [1,2,3,4]:     │
│    for variable in [8 vars]:   │
│      1. Lee ventana histórica  │
│      2. Ajusta Ridge           │
│      3. Proyecta 3 pasos       │
│      4. Escribe real+predicho  │
└───────────┬────────────────────┘
            │ write
            ▼
   agro_iot_ml (InfluxDB)
   measurement: sensor_forecast
   tags: parcela, variable, type=[real|predicted]
   field: value
            │
            ▼
        Grafana
   8 paneles × "Real vs Predicho"
   línea sólida vs línea punteada
```

---

## Cambios al proyecto para integrar esta fase

### Archivos nuevos

```
fase_6/
├── ml_service.py        ← servicio de predicción (este archivo)
├── Dockerfile           ← imagen Docker independiente
├── requirements.txt     ← scikit-learn, pandas, numpy, influxdb-client
└── README.md            ← este archivo
```

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `gateway_iot/docker-compose.yml` | Agregado servicio `ml_service` con build en `../fase_6` |
| `gateway_iot/grafana/provisioning/datasources/influxdb.yaml` | Agregado datasource `InfluxDB-ML` apuntando a bucket `agro_iot_ml` |
| `gateway_iot/grafana/provisioning/dashboards/agro_dashboard.json` | Agregada sección "Fase 6" con 8 paneles Real vs Predicho |

### Nuevo bucket en InfluxDB

El servicio crea automáticamente `agro_iot_ml` al arrancar. Estructura de datos:

```
measurement: sensor_forecast
tags:
  parcela:  parcela_1 | parcela_2 | parcela_3 | parcela_4
  cultivo:  sugarcane | oil_palm
  variable: temperature_air | humidity | rainfall | ...
  type:     real | predicted
fields:
  value: float
```

---

## Cómo correr todo

```bash
cd gateway_iot
sudo docker-compose down
sudo docker-compose up --build
```

Los primeros datos aparecen en Grafana ~90 segundos después de que el simulador empieza a enviar datos. El servicio ML espera 60s iniciales para que `agro_iot_processed` tenga suficientes puntos antes de hacer la primera predicción.

### Verificar que el servicio funciona

```bash
sudo docker logs iot_ml_service -f
```

Output esperado:
```
Fase 6 — Predicción de Variables Agroclimáticas
Variables: 8 | Parcelas: 4 | Horizonte: 3 pasos (~5 min)
✔ Conectado a InfluxDB (http://influxdb:8086)
Esperando datos iniciales del simulador (60s)...
Iniciando ciclo de predicción cada 30s.
Ciclo OK — 32/32 predicciones escritas — 2.3s
```

32 = 4 parcelas × 8 variables. Si aparece un número menor, algunas variables todavía no tienen suficientes puntos (mínimo 5).