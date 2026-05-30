# Variables Calculadas — Gateway IoT Agrícola

Todas las variables derivadas son calculadas por el `DataEnricher` (`processors/enricher.py`)
a partir de las lecturas crudas validadas. Las fórmulas están implementadas en
`processors/agronomic.py`.

---

## 1. VPD — Vapor Pressure Deficit

**¿Para qué sirve?**
Mide cuánta agua puede "absorber" el aire. Es el indicador principal de estrés
foliar por transpiración: si el VPD es muy alto, el cultivo cierra sus estomas
para no perder agua y la fotosíntesis se detiene.

**Cómo se calcula:**
```
es = 0.6108 * exp((17.27 * T) / (T + 237.3))   ← presión de vapor saturada (Tetens, FAO-56)
ea = es * RH / 100                               ← presión de vapor real
VPD = max(0, es - ea)                            ← déficit (kPa)
```

**Entradas:** `temperature_air` (T, °C), `humidity` (RH, %)

**Interpretación:**

| VPD (kPa) | Estado |
|-----------|--------|
| < 0.5     | Ambiente muy húmedo — riesgo de enfermedades fúngicas |
| 0.5–1.5   | Óptimo — transpiración y fotosíntesis activas |
| 1.5–3.0   | Estrés moderado |
| > 3.0     | Estrés severo — cierre estomático |

**Umbral de alerta:** Caña: > 3.0 kPa | Palma: > 2.5 kPa

---

## 2. Dew Point — Punto de Rocío

**¿Para qué sirve?**
Temperatura a la que el aire se satura y el agua se condensa sobre las hojas.
Si la temperatura nocturna cae al punto de rocío, aumenta el riesgo de
enfermedades fúngicas y bacterianas.

**Cómo se calcula:**
```
gamma = (17.27 * T) / (237.7 + T) + ln(RH / 100)
Td = (237.7 * gamma) / (17.27 - gamma)            ← fórmula de Magnus (°C)
```

**Entradas:** `temperature_air` (T, °C), `humidity` (RH, %)

**Interpretación:** Si `temperature_air` ≈ `dew_point`, hay riesgo de condensación
en hojas y aparición de enfermedades fúngicas.

---

## 3. THI — Temperature-Humidity Index

**¿Para qué sirve?**
Índice integral de bochorno que combina temperatura y humedad en un único
número. Originalmente diseñado para estrés en ganado (NRC, 1971), se aplica
también como indicador de confort térmico y estrés en cultivos sensibles.

**Cómo se calcula:**
```
THI = (1.8 * T + 32) - (0.55 - 0.0055 * RH) * (1.8 * T - 26)
```

**Entradas:** `temperature_air` (T, °C), `humidity` (RH, %)

**Interpretación:**

| THI | Estado |
|-----|--------|
| < 72 | Normal |
| 72–79 | Estrés leve |
| 80–89 | Estrés moderado |
| ≥ 90 | Estrés severo |

---

## 4. Heat Index — Índice de Estrés Calórico

**¿Para qué sirve?**
Indicador continuo (0–1) de cuánto estrés calórico sufre el cultivo respecto a
su temperatura óptima. A diferencia del flag binario `heat_stress_index`, este
índice matiza la intensidad del estrés.

**Cómo se calcula:**
```
deviation = max(0, T - Topt)
base = tanh(deviation / 8.0)               ← saturación suave a partir de +10°C sobre Topt

Si RH > 60%:
  base = min(1.0, base * (1 + (RH - 60) / 80))   ← humedad agrava el estrés
```

**Entradas:** `temperature_air` (T, °C), `humidity` (RH, %)

**Constante por cultivo (Topt):**
- Caña de azúcar: 27.0 °C
- Palma de aceite: 28.0 °C

**Interpretación:**

| Heat Index | Estado |
|------------|--------|
| 0.0 | Temperatura óptima |
| 0.3 | Borde del rango aceptable |
| 1.0 | Estrés extremo |

---

## 5. ETo — Evapotranspiración de Referencia

**¿Para qué sirve?**
Estima cuánta agua pierde el suelo y las plantas al día (en mm). Es la base para
calcular cuánto hay que regar. Un ETo alto significa que el cultivo demanda más
agua para compensar las pérdidas.

**Cómo se calcula:**

**Fórmula principal — Jensen-Haise simplificada (FAO):**
```
ETo = (0.025 * T + 0.078) * Rs / 2.45    (mm/día)
```
Donde Rs es la radiación solar en MJ/m²/día y 2.45 convierte energía a
altura de agua equivalente.

**Fallback — Hargreaves-Samani** (cuando no hay piranómetro):
```
ETo = 0.0023 * (T + 17.8) * sqrt(10) * 33 / 2.45
```
Se usa Ra = 33 MJ/m²/d (radiación extraterrestre típica del trópico) y
rango térmico diurno estimado de 10 °C.

**Entradas:** `temperature_air` (T, °C), `solar_radiation` (Rs, MJ/m²/d) — opcional

**Umbral de alerta:** > 9.0 mm/d (ambos cultivos) → demanda hídrica extrema

---

## 6. ETc — Requerimiento Hídrico del Cultivo

**¿Para qué sirve?**
Es el agua que necesita específicamente ese cultivo por día. Se diferencia del
ETo en que ETo mide el potencial evaporativo del ambiente; ETc lo ajusta al
cultivo real mediante el coeficiente Kc.

**Cómo se calcula:**
```
ETc = ETo * Kc    (mm/día)
```

**Entradas:** `evapotranspiration` (ETo), coeficiente Kc del cultivo

**Coeficiente Kc por cultivo (FAO-56):**
- Caña de azúcar: Kc = 1.25 (fase de máximo desarrollo, Inman-Bamber 1994)
- Palma de aceite: Kc = 1.00 (promedio anual, Corley & Tinker 2016)

---

## 7. Water Balance — Balance Hídrico

**¿Para qué sirve?**
Indica si está lloviendo lo suficiente para cubrir las necesidades del cultivo.
Un balance negativo significa que hay que regar; positivo, que hay superávit
de agua.

**Cómo se calcula:**
```
rainfall_daily = rainfall_mensual / 30     ← lluvia mensual convertida a diaria
water_balance = rainfall_daily - ETc       (mm/día)
```

**Entradas:** `rainfall` (mm/mes), `crop_water_requirement` (ETc)

**Interpretación:**

| Balance (mm/día) | Estado |
|------------------|--------|
| > 0 | Superávit — sobra agua |
| < 0 | Déficit — necesita riego |

---

## 8. GDD — Growing Degree Days (Incremento)

**¿Para qué sirve?**
Mide el calor acumulado que recibe el cultivo, que determina su ritmo de
crecimiento y desarrollo. Las plantas no crecen por debajo de una temperatura
base (Tbase). Al acumular suficientes GDD se pueden estimar fechas de
floración y cosecha.

**Cómo se calcula:**
```
GDD_incremento = max(0, T - Tbase)    (°C por lectura)
```

Se acumula diariamente en InfluxDB con `aggregateWindow(sum)`.

**Entradas:** `temperature_air` (T, °C), Tbase del cultivo

**Temperatura base (Tbase) por cultivo:**
- Caña de azúcar: 18.0 °C
- Palma de aceite: 15.0 °C

---

## 9. Disease Risk — Riesgo de Enfermedad

**¿Para qué sirve?**
Score de 0 a 1 que estima la probabilidad de aparición de patógenos foliares
según las condiciones climáticas actuales. Permite activar aplicaciones
preventivas de fungicidas antes de que aparezca la enfermedad visible.

**Cómo se calcula — Caña de azúcar (Roya naranja / Mancha amarilla):**
```
Si T fuera de rango [20, 32°C]: disease_risk = 0

Si RH < 75%:
  disease_risk = (RH / 75) * 0.30     ← riesgo bajo de fondo

Si RH >= 75%:
  temp_factor = 1 - abs(T - 26) / 8   ← óptimo del patógeno ≈ 26°C
  hum_factor  = min(1, (RH - 75) / 20)
  disease_risk = temp_factor * hum_factor
```

**Cómo se calcula — Palma de aceite (Pudrición del cogollo / Ganoderma):**
```
score = 0
Si T > 26°C:           score += min(1, (T - 26) / 6) * 0.30
Si RH > 80%:           score += min(1, (RH - 80) / 15) * 0.40
Si soil_moisture > 65%: score += min(1, (sm - 65) / 20) * 0.30

disease_risk = min(1.0, score)
```

**Entradas:** `temperature_air`, `humidity`, `soil_moisture` (solo palma)

**Umbral de alerta:** > 0.70 (ambos cultivos)

---

## 10. Irrigation Need — Necesidad de Riego

**¿Para qué sirve?**
Indicador integrado (0–1) que combina la humedad del suelo y el balance hídrico
para recomendar cuándo y con qué urgencia hay que regar. Es más preciso que
usar solo la humedad del suelo porque también considera si está lloviendo.

**Cómo se calcula:**
```
deficit_ratio = max(0, (sm_low - soil_moisture) / sm_low)
need = min(1.0, deficit_ratio)

Si water_balance < 0:
  need = min(1.0, need + abs(water_balance) / 10.0)   ← balance negativo aumenta urgencia
```

**Entradas:** `soil_moisture`, umbral mínimo del cultivo (`sm_low`), `water_balance`

**Umbral mínimo de humedad de suelo (sm_low) por cultivo:**
- Caña de azúcar: 15 %
- Palma de aceite: 30 %

**Interpretación:**

| Irrigation Need | Acción |
|-----------------|--------|
| 0.0 | Sin necesidad de riego |
| 0.5 | Déficit moderado — planificar riego |
| > 0.6 | **Alerta** — iniciar riego |
| 1.0 | Riego de emergencia |

---

## 11. Heat Stress Index (Flag binario)

**¿Para qué sirve?**
Flag de compatibilidad (0 o 1) para alertas en Grafana. Indica de forma binaria
si la temperatura supera el umbral máximo del cultivo. Complementa al `heat_index`
continuo.

**Cómo se calcula:**
```
heat_stress_index = 1.0 si temperature_air > threshold_high
                    0.0 si temperature_air ≤ threshold_high
```

**Umbral alto por cultivo:** 35 °C (caña y palma)

---

## 12. Water Stress Flag (Flag binario)

**¿Para qué sirve?**
Flag de compatibilidad (0 o 1) para alertas en Grafana. Indica de forma binaria
si la humedad del suelo cayó bajo el mínimo crítico del cultivo.

**Cómo se calcula:**
```
water_stress_flag = 1.0 si soil_moisture < threshold_low
                    0.0 si soil_moisture ≥ threshold_low
```

**Umbral mínimo por cultivo:** Caña: 15 % | Palma: 30 %

---

## 13. Quality Score

**¿Para qué sirve?**
Mide la calidad del payload recibido. Si varios sensores enviaron valores fuera
de rango físico o no numéricos, el quality score baja. Permite detectar fallos
de hardware o conectividad antes de que afecten los indicadores derivados.

**Cómo se calcula:**
```
quality_score = campos_válidos / (campos_válidos + campos_inválidos)
```

**Rango:** 0.0 (todos los campos inválidos) a 1.0 (todos los campos válidos)

**Umbral de alerta:** < 0.70 → más del 30 % de los campos son inválidos

---

## Resumen de Variables

| Variable | Unidad | Entradas | Fórmula base |
|----------|--------|----------|--------------|
| `vpd` | kPa | T, RH | Tetens (FAO-56) |
| `dew_point` | °C | T, RH | Magnus |
| `thi` | índice | T, RH | NRC 1971 |
| `heat_index` | 0–1 | T, RH, Topt | tanh continuo |
| `evapotranspiration` (ETo) | mm/d | T, Rs | Jensen-Haise / Hargreaves |
| `crop_water_requirement` (ETc) | mm/d | ETo, Kc | ETc = ETo × Kc |
| `water_balance` | mm/d | rainfall, ETc | lluvia_diaria − ETc |
| `gdd_increment` | °C | T, Tbase | max(0, T − Tbase) |
| `disease_risk` | 0–1 | T, RH, SM | Modelo por cultivo |
| `irrigation_need` | 0–1 | SM, sm_low, WB | Déficit + balance |
| `heat_stress_index` | 0 o 1 | T, umbral | Flag binario |
| `water_stress_flag` | 0 o 1 | SM, umbral | Flag binario |
| `quality_score` | 0–1 | campos validados | válidos / total |
