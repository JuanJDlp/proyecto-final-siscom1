"""
Cálculo de indicadores agronómicos derivados.

Cada función devuelve None si faltan las entradas necesarias.
Las fórmulas están referenciadas a literatura estándar y se documentan
en gateway_iot/README.md §6.

Convenciones:
  T  → temperatura del aire (°C)
  RH → humedad relativa (%)
  Rs → radiación solar global (MJ/m²/día)
  u  → velocidad del viento (km/h)
"""

import math
from typing import Optional


# ─── Presión de vapor y déficit (VPD) ─────────────────────────────────────────

def saturation_vapor_pressure(T: float) -> float:
    """Presión de vapor de saturación (kPa) — fórmula de Tetens (FAO-56)."""
    return 0.6108 * math.exp((17.27 * T) / (T + 237.3))


def compute_vpd(T: Optional[float], RH: Optional[float]) -> Optional[float]:
    """Vapor Pressure Deficit (kPa).

    Indicador #1 de estrés foliar por transpiración:
      VPD < 0.5 kPa  → cultivo poco activo, ambiente muy húmedo (riesgo de enfermedades)
      0.5–1.5 kPa    → óptimo de transpiración y fotosíntesis
      1.5–3.0 kPa    → estrés moderado
      > 3.0 kPa      → estrés severo, cierre estomático
    """
    if T is None or RH is None:
        return None
    es = saturation_vapor_pressure(T)
    ea = es * RH / 100.0
    return round(max(0.0, es - ea), 3)


def compute_dew_point(T: Optional[float], RH: Optional[float]) -> Optional[float]:
    """Punto de rocío (°C) — Magnus.

    Si la temperatura mínima del día cae al punto de rocío, se condensa
    agua en hojas y aumenta el riesgo de enfermedades fúngicas.
    """
    if T is None or RH is None or RH <= 0:
        return None
    a, b = 17.27, 237.7
    gamma = (a * T) / (b + T) + math.log(RH / 100.0)
    return round((b * gamma) / (a - gamma), 2)


# ─── Índices de calor ─────────────────────────────────────────────────────────

def compute_thi(T: Optional[float], RH: Optional[float]) -> Optional[float]:
    """Temperature-Humidity Index (NRC, 1971).

    Originalmente diseñado para estrés en ganado, también se usa como
    índice integral de bochorno para cultivos sensibles:
      < 72  → normal
      72–79 → estrés leve
      80–89 → estrés moderado
      ≥ 90  → estrés severo
    """
    if T is None or RH is None:
        return None
    return round((1.8 * T + 32.0) - (0.55 - 0.0055 * RH) * (1.8 * T - 26.0), 2)


def compute_heat_index(T: Optional[float], Topt: float, RH: Optional[float]) -> Optional[float]:
    """Índice de estrés calórico continuo (0–1), ponderado por humedad.

    Reemplaza al heat_stress_index binario:
      0    → temperatura óptima
      0.3  → bordes del rango aceptable
      1.0  → estrés extremo
    """
    if T is None:
        return None
    deviation = max(0.0, T - Topt)
    # crece como tanh — saturación suave a partir de +10°C sobre Topt
    base = math.tanh(deviation / 8.0)
    if RH is not None and RH > 60:
        # la humedad alta agrava el estrés calórico
        base = min(1.0, base * (1.0 + (RH - 60.0) / 80.0))
    return round(base, 3)


# ─── Evapotranspiración y balance hídrico ─────────────────────────────────────

def compute_eto(T: Optional[float], Rs: Optional[float]) -> Optional[float]:
    """Evapotranspiración de referencia ETo (mm/día) — Jensen-Haise simplificada.

      ETo = (0.025·T + 0.078) · Rs / 2.45

    Donde Rs viene en MJ/m²/día. La constante 2.45 convierte energía a
    altura de agua equivalente. Funciona bien en zonas tropicales como
    el Valle del Cauca.

    Si no hay radiación, se cae a Hargreaves-Samani con Ra=33 MJ/m²/d
    (radiación extraterrestre típica del trópico) y rango térmico
    diurno estimado en 10°C.
    """
    if T is None:
        return None
    if Rs is not None and Rs > 0:
        return round((0.025 * T + 0.078) * Rs / 2.45, 3)
    # Fallback Hargreaves cuando no hay piranómetro en la parcela
    return round(0.0023 * (T + 17.8) * math.sqrt(10.0) * 33.0 / 2.45, 3)


def compute_crop_water_requirement(ETo: Optional[float], Kc: float) -> Optional[float]:
    """Requerimiento hídrico del cultivo ETc = ETo · Kc (mm/día)."""
    if ETo is None:
        return None
    return round(ETo * Kc, 3)


def compute_water_balance(rainfall_monthly_mm: Optional[float],
                          ETc: Optional[float]) -> Optional[float]:
    """Balance hídrico diario estimado (mm/día).

    Convierte la lluvia mensual del dataset a una tasa diaria equivalente
    y la resta del requerimiento hídrico del cultivo:
      balance = (rainfall_mensual / 30) − ETc
      balance > 0  → superávit (sobra agua)
      balance < 0  → déficit (hay que regar)
    """
    if rainfall_monthly_mm is None or ETc is None:
        return None
    rainfall_daily = rainfall_monthly_mm / 30.0
    return round(rainfall_daily - ETc, 3)


# ─── Recomendación de riego ───────────────────────────────────────────────────

def compute_irrigation_need(soil_moisture: Optional[float],
                            sm_low: Optional[float],
                            water_balance: Optional[float]) -> Optional[float]:
    """Indicador continuo de necesidad de riego (0–1).

    0    → el cultivo no necesita riego inmediato
    0.5  → empieza a haber déficit
    1.0  → riego de emergencia
    """
    if soil_moisture is None or sm_low is None or sm_low <= 0:
        return None
    deficit_ratio = max(0.0, (sm_low - soil_moisture) / sm_low)
    need = min(1.0, deficit_ratio)
    if water_balance is not None and water_balance < 0:
        # un balance hídrico negativo aumenta la urgencia
        need = min(1.0, need + abs(water_balance) / 10.0)
    return round(need, 3)


# ─── Growing Degree Days ──────────────────────────────────────────────────────

def compute_gdd_increment(T: Optional[float], Tbase: float) -> Optional[float]:
    """Incremento de GDD para esta lectura: max(0, T − Tbase).

    Acumulado en el dashboard vía aggregateWindow(sum) sobre 1 día,
    permite estimar fenología (días térmicos hasta floración, cosecha…).
    """
    if T is None:
        return None
    return round(max(0.0, T - Tbase), 3)


# ─── Riesgo de enfermedad ─────────────────────────────────────────────────────

def compute_disease_risk_sugarcane(T: Optional[float],
                                   RH: Optional[float]) -> Optional[float]:
    """Riesgo de enfermedades foliares en caña (Roya naranja, Mancha amarilla).

    Las royas y manchas foliares prosperan con:
      20°C ≤ T ≤ 30°C  Y  HR > 80%

    Score 0–1 ponderado por cuán dentro de esa ventana se encuentra.
    """
    if T is None or RH is None:
        return None
    if not (20.0 <= T <= 32.0):
        return 0.0
    if RH < 75.0:
        return round((RH / 75.0) * 0.3, 3)  # riesgo bajo de fondo
    temp_factor = 1.0 - abs(T - 26.0) / 8.0       # óptimo de patógeno ≈ 26°C
    hum_factor  = min(1.0, (RH - 75.0) / 20.0)
    score = max(0.0, temp_factor) * hum_factor
    return round(score, 3)


def compute_disease_risk_palm(T: Optional[float],
                              RH: Optional[float],
                              soil_moisture: Optional[float]) -> Optional[float]:
    """Riesgo de pudrición del cogollo / Ganoderma en palma de aceite.

    Condiciones favorables al patógeno:
      T > 26°C, HR > 85%, suelo encharcado (soil_moisture > 65%)
    """
    if T is None or RH is None:
        return None
    score = 0.0
    if T > 26.0:
        score += min(1.0, (T - 26.0) / 6.0) * 0.30
    if RH > 80.0:
        score += min(1.0, (RH - 80.0) / 15.0) * 0.40
    if soil_moisture is not None and soil_moisture > 65.0:
        score += min(1.0, (soil_moisture - 65.0) / 20.0) * 0.30
    return round(min(1.0, score), 3)


def compute_disease_risk(cultivo: str,
                         T: Optional[float],
                         RH: Optional[float],
                         soil_moisture: Optional[float]) -> Optional[float]:
    """Selector por cultivo."""
    if cultivo == "sugarcane":
        return compute_disease_risk_sugarcane(T, RH)
    if cultivo == "oil_palm":
        return compute_disease_risk_palm(T, RH, soil_moisture)
    return None
