# Análisis EDA Agroclimático — Fase 1
## Sistema IoT para Agricultura Digital

**Proyecto Final · Sistemas y Comunicaciones I**
**Universidad ICESI · Departamento de Computación y Sistemas Inteligentes**
**Fecha:** Mayo 2026

---

## NOTA IMPORTANTE

**Este documento es un RESUMEN EJECUTIVO.** El análisis completo y detallado se encuentra en el **Jupyter Notebook: `eda_agroclimatico.ipynb`**

El notebook contiene:
- Carga y exploración de datos
- Limpieza y validación
- Estadísticas descriptivas y correlaciones
- Análisis de impacto de variables (Random Forest)
- Comportamiento de variables en condiciones de alto/bajo rendimiento
- **Análisis contextual: Temperaturas para el Valle del Cauca** ← Incluye datos de Colombia
- Validación cruzada entre datasets

Este documento resume los hallazgos principales y recomendaciones para la Fase 2.

---

## 1. Introducción

Este documento consolida los **hallazgos principales** del Análisis Exploratorio de Datos (EDA) realizado sobre tres datasets agroclimáticos públicos, como parte de la Fase 1 del proyecto de simulación de un sistema IoT para agricultura digital.

Los cultivos objetivo del proyecto son:
- **Caña de azúcar** (*Saccharum officinarum*)
- **Palma de aceite** (*Elaeis guineensis*)

El objetivo de esta fase fue comprender la estructura, calidad y distribución estadística de los datos disponibles, e identificar cuantitativamente qué variables agroclimáticas impactan más el rendimiento de cada cultivo y cómo deben comportarse. Esta información fundamenta la selección de variables para el simulador de sensores IoT (Fase 2) y la definición de umbrales de alerta (Fase 5).

---

## 2. Datasets Utilizados

### 2.1 `sugarcane-prediction-dataset.csv` — Dataset principal

| Atributo | Valor |
|---|---|
| Registros | 3.000 |
| Variables | 81 |
| Origen | Datos de campo agrícola (India) |
| Tipo de datos | Agroclimáticos, edáficos, de manejo y rendimiento |
| Valores nulos | 80/81 columnas con nulos (promedio ~4%) |
| Duplicados | 0 |

**Variables disponibles por categoría:**

| Categoría | Variables |
|---|---|
| Climáticas | `Temp_Min_C`, `Temp_Max_C`, `Temp_Avg_C`, `Rainfall_Total_mm`, `Humidity_%`, `Solar_Radiation_MJ_m2_day`, `Wind_Speed_kmph`, `Evapotranspiration_mm_day`, `Dew_Point_C` |
| Edáficas | `Soil_Type`, `Soil_pH`, `Soil_Moisture_%`, `Organic_Carbon_%`, `Sand_%`, `Silt_%`, `Clay_%`, `Soil_Depth_cm` |
| Nutrientes | `Nitrogen_kg_per_acre`, `Phosphorus_kg_per_acre`, `Potassium_kg_per_acre`, `Zinc_mg_per_kg`, `Iron_mg_per_kg` |
| Manejo | `Irrigation_Frequency_Level`, `Fertilizer_Type`, `Planting_Method`, `Disease_Type` |
| Rendimiento | `Yield_Quintal_per_Acre` |

### 2.2 `sugarcane-dataset-2.csv` — Dataset simplificado

| Atributo | Valor |
|---|---|
| Registros originales | 120 |
| Registros tras limpieza | 90 (30 duplicados eliminados) |
| Variables | 12 |
| Valores nulos | 0 |

Dataset reducido que cubre lluvia, temperatura, horas de sol, nutrientes (N, P, K), tipo de suelo, duración del cultivo y rendimiento. Útil para prototipado rápido.

### 2.3 `crop-production-countries.csv` — Dataset global de producción

| Atributo | Valor |
|---|---|
| Registros | 24.500 |
| Variables | 16 |
| Período | 2000–2024 |
| Cobertura | Múltiples países y cultivos |
| Valores nulos | 0 |

Contiene datos agregados por país y año: producción, rendimiento, lluvia anual, temperatura, fertilizantes e irrigación. Es la **única fuente con datos de palma de aceite** (375 registros) en el proyecto.

---

## 3. Limpieza y Validación de Datos

### 3.1 Estrategia de limpieza

| Problema | Acción tomada | Justificación |
|---|---|---|
| Nulos en variables Tier 1 simultáneos | Eliminación de la fila | Sin datos climáticos clave la fila no aporta |
| Nulos individuales < 15% | Imputación con mediana | Conserva información; evita sesgo |
| Duplicados en `dataset-2` | Eliminación (30 filas) | Duplicados exactos no aportan variabilidad |
| Outliers en lluvia/temperatura | **Conservados** | Representan eventos climáticos reales (sequías, lluvias extremas) |

### 3.2 Resultado de la limpieza

Tras la limpieza no se perdió ninguna observación del dataset principal. Los outliers se documentaron como información válida para futuros umbrales de alerta.

---

## 4. Estadísticas Descriptivas — Variables Clave

### 4.1 Caña de azúcar (`sugarcane-prediction-dataset`, n=3.000)

| Variable | Media | Mediana | Desv. Est. | Mín | Máx |
|---|---|---|---|---|---|
| Temperatura promedio (°C) | 27.85 | 27.84 | 8.24 | 10.0 | 44.9 |
| Temperatura mínima (°C) | 22.35 | 22.31 | 8.28 | 2.3 | 41.3 |
| Temperatura máxima (°C) | 33.36 | 33.23 | 8.32 | 13.1 | 52.5 |
| Precipitación (mm/mes) | 1 399 | 1 397 | 334.8 | 800.2 | 1 999 |
| Humedad relativa (%) | 70.05 | 69.91 | 11.30 | 50.0 | 90.0 |
| Radiación solar (MJ/m²/d) | 22.56 | 22.54 | 4.30 | 15.0 | 30.0 |
| Velocidad viento (km/h) | 8.61 | 8.78 | 3.66 | 2.0 | 15.0 |
| Evapotranspiración (mm/d) | 5.01 | 5.02 | 1.69 | 2.0 | 8.0 |
| pH del suelo | 7.25 | 7.24 | 0.71 | 6.0 | 8.5 |
| Humedad del suelo (%) | 25.20 | 25.50 | 8.48 | 10.0 | 40.0 |
| **Rendimiento (quintal/acre)** | **280.24** | **281.07** | **104.10** | **40.2** | **606.5** |

### 4.2 Palma de aceite (`crop-production-countries`, n=375)

| Variable | Mediana | Referencia Caña |
|---|---|---|
| Temperatura promedio (°C) | 24.6 | 22.5 |
| Lluvia anual (mm) | 1 674 | 1 135 |
| Rendimiento (kg/ha) | 9 565 | 39 532* |

> \* El rendimiento de caña en kg/ha es muy superior porque el volumen de biomasa cosechada (tallo) es mucho mayor que el aceite extraído de la palma.

---

## 5. Análisis de Impacto de Variables sobre el Rendimiento

### 5.1 Metodología

Se usaron dos métodos complementarios para cuantificar el impacto de cada variable sobre el rendimiento:

1. **Correlación de Pearson** — relación lineal entre variable y rendimiento.
2. **Random Forest Regressor** — captura relaciones no lineales e interacciones entre variables. El modelo alcanzó un **R² = 0.766** (76.6% de la varianza del rendimiento explicada), lo que valida su capacidad predictiva.

### 5.2 Ranking de variables — Caña de Azúcar

#### Por correlación de Pearson con `Yield_Quintal_per_Acre`

| Posición | Variable | Correlación | Dirección |
|---|---|---|---|
| 1 | `Nitrogen_kg_per_acre` | r = **+0.4604** | Positiva — más N → mayor rendimiento |
| 2 | `Potassium_kg_per_acre` | r = **+0.2257** | Positiva — K esencial para síntesis de azúcar |
| 3 | `Soil_Moisture_%` | r = **+0.1274** | Positiva — suelo húmedo favorece el crecimiento |
| 4 | `Temp_Avg_C` | r = **+0.1265** | Positiva — temperaturas más cálidas (en rango) mejoran rendimiento |
| 5 | `Temp_Max_C` | r = **+0.1251** | Positiva |
| 6 | `Temp_Min_C` | r = **+0.1242** | Positiva |
| 7 | `Rainfall_Total_mm` | r = **+0.0868** | Positiva — más lluvia → mayor producción |
| 8 | `Humidity_%` | r = **+0.0677** | Positiva — humedad ambiental beneficia el cultivo |

#### Por importancia Random Forest

| Posición | Variable | Importancia RF |
|---|---|---|
| 1 | `Nitrogen_kg_per_acre` | 0.2912 (29.1%) |
| 2 | `Potassium_kg_per_acre` | 0.0799 (8.0%) |
| 3 | `Soil_Moisture_%` | 0.0374 (3.7%) |
| 4 | `Temp_Max_C` | 0.0231 (2.3%) |
| 5 | `Rainfall_Total_mm` | 0.0200 (2.0%) |
| 6 | `Humidity_%` | 0.0179 (1.8%) |

> **Hallazgo clave:** El Nitrógeno domina ambos rankings con diferencia. Aunque no es una variable climática pura, es un nutriente cuya disponibilidad depende de la humedad del suelo y el pH — variables que sí se monitorean con sensores IoT. Esto confirma que el monitoreo del suelo (pH, humedad, nutrientes) es tan crítico como el monitoreo climático.

### 5.3 Análisis de palma de aceite (dataset global)

Las correlaciones con rendimiento en el dataset global muestran que para palma de aceite la **lluvia anual** es la variable climática más determinante, seguida de la temperatura. Esto es coherente con la biología de la palma: es un cultivo de zonas húmedas tropicales que requiere precipitación constante.

---

## 6. Comportamiento de Variables: Alto vs. Bajo Rendimiento

### 6.1 Metodología

El dataset de caña se dividió en cuartiles de rendimiento:
- **Q1 — Bajo rendimiento:** < 205.4 quintal/acre (n = 750)
- **Q4 — Alto rendimiento:** > 356.4 quintal/acre (n = 750)

Se compararon las medianas de las variables clave entre ambos grupos.

### 6.2 Resultados comparativos

| Variable | Q1 (Bajo) | Q4 (Alto) | Diferencia | Interpretación |
|---|---|---|---|---|
| Temperatura promedio (°C) | 27.10 | 28.69 | **+5.9%** | El cultivo rinde más en rangos más cálidos (dentro del óptimo) |
| Precipitación (mm/mes) | 1.363 | 1.450 | **+6.4%** | Más lluvia disponible en condiciones de alto rendimiento |
| Humedad relativa (%) | 69.64 | 71.01 | **+2.0%** | Diferencia pequeña pero consistente |
| pH del suelo | 7.24 | 7.24 | **~0%** | El pH no discrimina entre rangos; la caña tolera todo el rango 6–8.5 |
| **Humedad del suelo (%)** | **23.86** | **27.01** | **+13.2%** | **Mayor diferenciador absoluto — crítico para el riego** |
| Radiación solar (MJ/m²/d) | 22.54 | 22.54 | **~0%** | No discrimina; el dataset cubre condiciones similares de radiación |
| Velocidad viento (km/h) | 8.67 | 8.81 | **+1.6%** | Diferencia mínima |
| Evapotranspiración (mm/d) | 5.02 | 5.02 | **~0%** | Ligada a temperatura y viento; sin diferencia neta |

### 6.3 Conclusión del análisis Q1 vs Q4

La **humedad del suelo** es la variable que más cambia entre condiciones de bajo y alto rendimiento (+13.2%). Esto la convierte en el **indicador operacional más importante** para el sistema IoT: cuando la humedad del suelo cae por debajo del umbral (~24%), el cultivo entra en estrés hídrico y el rendimiento se ve comprometido.

La temperatura y la lluvia también discriminan positivamente, aunque en menor magnitud. El pH y la radiación solar son relativamente estables en el dataset y no discriminan significativamente entre Q1 y Q4.

---

## 7. Comportamiento Esperado de Variables Clave

### 7.1 Caña de azúcar — Rangos óptimos y señales de alarma

**Nota sobre contextualización local:** Los rangos óptimos mostrados reflejan condiciones de alto rendimiento en contextos cálido-húmedos (datos de India, media 27.9°C). Para aplicación en **Valle del Cauca** (rango local 20-32°C), se utiliza un rango óptimo más conservador basado en datos reales de caña en Colombia (27.1°C media, 2503 mm/año).

| Variable | Rango Normal (datos) | Rango Óptimo — Global | Rango Óptimo — Valle del Cauca* | Alerta Baja | Alerta Alta |
|---|---|---|---|---|---|
| Temperatura (°C) | 10–45 | 28–35 | **20–30** | < 18 °C | > 38 °C |
| Lluvia (mm/mes) | 800–2000 | 1350–1550 | 1200–1800 | < 900 mm | > 1900 mm |
| Humedad relativa (%) | 50–90 | 69–75 | 65–75 | < 55% | > 88% |
| pH suelo | 6.0–8.5 | 6.5–7.9 | 6.0–7.5 | < 5.5 | > 8.5 |
| Humedad suelo (%) | 10–40 | 25–32 | 24–32 | **< 15%** | > 40% |
| Radiación solar (MJ/m²/d) | 15–30 | 18–26 | 18–26 | < 12 | > 28 |
| Viento (km/h) | 2–15 | 5–12 | 4–10 | — | > 40 |
| Evapotranspiración (mm/d) | 2–8 | 3–7 | 3–6 | — | > 9 |

> \* Rango óptimo del Valle del Cauca basado en datos reales de caña en Colombia (dataset global, 2000-2024). Temperatura promedio colombiana: 27.1°C; precipitación: 2503 mm/año. Estos datos validan la viabilidad del cultivo en el rango 20-32°C de la región.

### 7.2 Palma de aceite — Variables agroclimáticas críticas (Tabla 2)

**Tabla 2. Variables agroclimáticas críticas para el cultivo de palma de aceite.**

| Variable | Rango óptimo | Efecto sobre el cultivo | Sensor utilizado |
|---|---|---|---|
| Temperatura del aire | 24 – 32 °C | Debajo de 18 °C se inhibe la polinización y el cuajado de frutos. Sobre 38 °C se daña el meristemo apical. | DHT22 / SHT35 |
| Precipitación / Riego | 1800 – 2500 mm/año | La distribución uniforme es determinante. Un déficit sostenido por más de tres meses reduce la producción de RFF en el ciclo siguiente. | Pluviómetro + caudalímetro |
| Radiación solar | > 1500 h sol/año | Factor limitante en la acumulación de aceite. Zonas con nubosidad persistente presentan rendimientos notoriamente inferiores. | Piranómetro CMP3 |
| Humedad relativa | 75 – 85 % | Favorece la actividad del insecto polinizador Elaeidobius kamerunicus. El HR inferior al 60 % genera estrés estomático. | BME680 / HIH6130 |
| Humedad del suelo | 40 – 80 % CC | El déficit sostenido provoca abscisión de frutos y reducción del peso medio de los racimos. | FDR / Tensiómetro |
| Velocidad del viento | < 7 m/s | Vientos fuertes rompen las hojas flecha en palmas jóvenes y complican la operación de cosecha. | Anemómetro de cazoletas |
| pH del suelo | 4.5 – 6.0 | La palma tolera suelos ácidos. pH superior a 7 limita la absorción de B, Mn y Zn, micronutrientes esenciales. | Electrodo de pH / lab. |
| Temperatura del suelo | 24 – 30 °C | Regula la actividad microbiana y la mineralización del nitrógeno, afectando la fertilidad disponible. | DS18B20 sonda |

---

## 8. Relación entre Datasets y Consistencia

### 8.1 Variables comunes entre datasets

Los tres datasets comparten columnas equivalentes de temperatura, lluvia y rendimiento, lo que permite validación cruzada:

| Variable | prediction (caña) | dataset-2 (caña) | countries (palma) |
|---|---|---|---|
| Temperatura media | 27.85 °C | 31.0 °C | 24.6 °C |
| Lluvia (referencia) | 1400 mm/mes | 1356 mm/año | 1674 mm/año |
| Disponibilidad | ✓ Alta (81 vars) | ✓ Media (12 vars) | ✓ Baja (4 vars clim.) |

### 8.2 Hallazgos de la comparación

- Los rangos de temperatura son **consistentes** entre los tres datasets, validando la calidad de los datos.
- La mayor lluvia de palma vs caña confirma la diferencia ecológica entre los dos cultivos.
- El dataset `sugarcane-dataset-2` funciona como un **subconjunto simplificado** del dataset principal, apropiado para prototipado rápido de modelos ML.
- El dataset global es la única fuente de palma de aceite y sus datos son a nivel de país/año (menos granulares que los otros dos).

### 8.3 Validación con contexto local (Colombia/Valle del Cauca)

**Caña de azúcar en Colombia** (datos del dataset global, 2000-2024):
- **Temperatura media:** 27.1°C (rango 24.7–29.8°C)
- **Precipitación anual:** 2503 mm/año (rango 1931–3042 mm)
- **Rendimiento:** 51,042 kg/ha
- **Validación:** El rango óptimo local de 20–30°C es **realista y conservador** para el Valle del Cauca, considerando que Colombia promedia 27.1°C. El máximo del Valle (32°C) solo se alcanza ocasionalmente.

**Palma de aceite en América Tropical** (datos globales, trópicos):
- **Temperatura media:** 24.8°C (rango 21.7–27.9°C en Indonesia, Malaysia, África)
- **Precipitación anual:** 2209 mm/año
- **Observación:** Colombia no tiene producción comercial de palma en el dataset global. Sin embargo, la palma crece exitosamente en zonas tropicales de América Latina. El rango óptimo de 24–32°C (Tabla 2) es biológicamente coherente con estas condiciones.

**Conclusión:** Los rangos documentados tienen **fundamento en datos reales** de la región latinoamericana, especialmente para caña. Para palma, aunque no hay producción comercial registrada en Colombia en el dataset global, el rango recomendado es coherente con las condiciones tropicales donde la palma crece exitosamente.

---

## 9. Variables Seleccionadas para el Sistema IoT

### 9.1 Justificación de la selección

La selección final de variables para el simulador de sensores IoT (Fase 2) combina:
- **Evidencia cuantitativa** del EDA (correlación, RF importance, análisis Q1 vs Q4).
- **Disponibilidad en el dataset** (la variable debe estar presente con suficientes datos).
- **Mensurabilidad con sensores IoT** reales (debe existir hardware comercial que la mida).

### 9.2 Variables seleccionadas — Tabla definitiva

| Variable IoT | Columna Dataset | Tier | Sensor físico | Frec. sugerida | Justificación |
|---|---|---|---|---|---|
| `temperature_air` | `Temp_Avg_C` | **1 — Crítica** | DHT22 / DS18B20 | Cada 15 min | Pos. 4 en correlación; +5.9% en Q4 vs Q1 |
| `humidity` | `Humidity_%` | **1 — Crítica** | DHT22 | Cada 15 min | Ligada a enfermedades; +2% en condiciones óptimas |
| `rainfall` | `Rainfall_Total_mm` | **1 — Crítica** | Pluviómetro | Acum. 1h | r=+0.09; +6.4% en Q4 vs Q1 |
| `soil_ph` | `Soil_pH` | **1 — Crítica** | Electrodo pH | Cada 2h | Controla absorción de nutrientes; rango diferente por cultivo |
| `soil_moisture` | `Soil_Moisture_%` | **1 — Crítica** | Sensor capacitivo | Cada 30 min | **Mayor discriminador Q4 vs Q1 (+13.2%)** |
| `solar_radiation` | `Solar_Radiation_MJ_m2_day` | 2 — Importante | Piranómetro | Cada 30 min | Clave para fotosíntesis; en top-10 RF |
| `wind_speed` | `Wind_Speed_kmph` | 2 — Importante | Anemómetro | Cada 15 min | Modula evapotranspiración |
| `evapotranspiration` | `Evapotranspiration_mm_day` | 2 — Importante | Calculada (gateway) | Diaria | Indicador integrado de balance hídrico |

### 9.3 Estructura de parcelas para la simulación

Según los requerimientos del proyecto (Fase 2), se simularán **4 parcelas agrícolas**:

| Parcela | Cultivo | Sensores activos |
|---|---|---|
| `parcela_1` | Caña de azúcar | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| `parcela_2` | Caña de azúcar | temperature_air, humidity, rainfall, wind_speed, evapotranspiration |
| `parcela_3` | Palma de aceite | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| `parcela_4` | Palma de aceite | temperature_air, humidity, rainfall, wind_speed |

### 9.4 Payload JSON que sera usado en la Fase 2

```json
{
  "timestamp": "2026-04-20 18:45:00",
  "parcela": "parcela_1",
  "cultivo": "sugarcane",
  "area_ha": 5.0,
  "temperature_air": 28.5,
  "humidity": 70.1,
  "rainfall": 1450.3,
  "soil_ph": 7.2,
  "soil_moisture": 27.0,
  "solar_radiation": 22.5
}
```

---

## 10. Resumen Ejecutivo

### Lo aprendido de los datos

1. **El Nitrógeno es el factor más correlacionado con el rendimiento de la caña** (r=+0.46, importancia RF=29.1%). Aunque es un nutriente de manejo, su disponibilidad depende de la humedad del suelo y el pH — variables monitoreables con sensores IoT.

2. **La humedad del suelo es el indicador operacional más crítico**: presenta la mayor diferencia relativa entre condiciones de alto y bajo rendimiento (+13.2%). Es la variable que más justifica la instalación de sensores de suelo en campo.

3. **La temperatura y la lluvia son las variables climáticas más impactantes** para ambos cultivos, con la diferencia de que la palma de aceite requiere un rango de temperatura más estrecho (24–32 °C) y significativamente más lluvia que la caña.

4. **El pH del suelo no discrimina** entre alto y bajo rendimiento para caña (rango 6–8.5 es amplio), pero **sí es crítico para palma** (requiere pH ácido 4–6) — el mismo sensor sirve a ambos cultivos pero con umbrales diferentes.

5. **Los tres datasets son consistentes** en rangos de temperatura y lluvia, lo que valida la calidad de los datos y permite usar el dataset global para contextualizar la palma de aceite a pesar de no tener datos a nivel de parcela.

6. **El modelo exploratorio Random Forest alcanzó R²=0.766**, indicando que las variables del dataset explican el 76.6% de la variabilidad en rendimiento. Esto representa una base sólida para los modelos de ML de la Fase 6.

---

## 11. Síntesis: Rangos Validados para el Valle del Cauca y Próximos Pasos

### 11.1 Rangos definitivos por cultivo

El análisis contextual completo (con datos reales de Colombia) se ejecuta en la **Sección 8 del notebook**. El resultado definitivo:

| Cultivo | Variable | Rango Óptimo Global | Rango Validado — Valle del Cauca | Fuente de validación |
|---|---|---|---|---|
| **Caña de azúcar** | Temperatura | 28–35°C | **20–30°C** | Colombia: 27.1°C (σ=1.3°C) |
| **Caña de azúcar** | Lluvia | 1200–1800 mm/mes | 1200–1800 mm/mes | Colombia: 2503 mm/año |
| **Palma de aceite** | Temperatura | 24–32°C | **24–32°C** | Trópicos: 24.8°C (σ=1.3°C) |
| **Palma de aceite** | Lluvia | 1800–2500 mm/año | **1800–2500 mm/año** | Indonesia/Malaysia/África |

**Conclusión:** Ambos cultivos son viables en el Valle del Cauca. La caña opera en el rango medio (24-30°C); la palma es más exigente y requiere al menos 24°C constantes.

### 11.2 Próximos pasos — Fase 2

Con base en este EDA, la Fase 2 debe:

1. Simular **4 parcelas** (2 caña + 2 palma) con los sensores de la Tabla 9.2
2. Usar los **rangos validados** de esta sección como límites del simulador
3. Generar distribuciones de datos sintéticos coherentes con las estadísticas del EDA (media, σ, percentiles)
4. Implementar sistema de comunicación IoT (MQTT/Kafka) para transmitir los payloads definidos en 9.4
5. Validar que los datos simulados reproduzcan las diferencias Q1 vs Q4 identificadas en la Sección 7
