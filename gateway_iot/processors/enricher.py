"""
DataEnricher — calcula todas las variables agronómicas derivadas
a partir de las lecturas crudas validadas.

Variables calculadas (ver gateway_iot/README.md §6 para fórmulas):
  · evapotranspiration  — ETo FAO Jensen-Haise
  · crop_water_requirement — ETc = ETo·Kc
  · water_balance       — lluvia_diaria − ETc
  · vpd                 — déficit de presión de vapor
  · dew_point           — punto de rocío
  · thi                 — Temperature-Humidity Index
  · heat_index          — estrés calórico continuo 0–1
  · gdd_increment       — grados-día sobre Tbase por lectura
  · disease_risk        — riesgo de enfermedad foliar/cogollo
  · irrigation_need     — necesidad de riego 0–1
  · heat_stress_index, water_stress_flag — flags binarios (compat.)
  · quality_score       — calidad de datos del payload
"""

from config.thresholds import CROP_CONSTANTS, THRESHOLDS
from models.sensor_reading import SensorReading
from processors import agronomic

SENSOR_FIELDS = [
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed",
]


class DataEnricher:
    def enrich(self, r: SensorReading) -> SensorReading:
        thresholds = THRESHOLDS.get(r.cultivo, {})
        constants  = CROP_CONSTANTS.get(r.cultivo, {"Tbase": 18.0, "Kc": 1.0, "Topt": 27.0})

        # ── Indicadores de humedad atmosférica ──
        r.vpd       = agronomic.compute_vpd(r.temperature_air, r.humidity)
        r.dew_point = agronomic.compute_dew_point(r.temperature_air, r.humidity)
        r.thi       = agronomic.compute_thi(r.temperature_air, r.humidity)
        r.heat_index = agronomic.compute_heat_index(
            r.temperature_air, constants["Topt"], r.humidity,
        )

        # ── Evapotranspiración y balance hídrico ──
        r.evapotranspiration   = agronomic.compute_eto(r.temperature_air, r.solar_radiation)
        r.crop_water_requirement = agronomic.compute_crop_water_requirement(
            r.evapotranspiration, constants["Kc"],
        )
        r.water_balance = agronomic.compute_water_balance(
            r.rainfall, r.crop_water_requirement,
        )

        # ── Fenología ──
        r.gdd_increment = agronomic.compute_gdd_increment(
            r.temperature_air, constants["Tbase"],
        )

        # ── Riesgo de enfermedad por cultivo ──
        r.disease_risk = agronomic.compute_disease_risk(
            r.cultivo, r.temperature_air, r.humidity, r.soil_moisture,
        )

        # ── Recomendación de riego ──
        sm_low = thresholds.get("soil_moisture", {}).get("low")
        r.irrigation_need = agronomic.compute_irrigation_need(
            r.soil_moisture, sm_low, r.water_balance,
        )

        # ── Flags binarios (mantenidos para alertas existentes y dashboard) ──
        temp_high = thresholds.get("temperature_air", {}).get("high")
        if r.temperature_air is not None and temp_high is not None:
            r.heat_stress_index = 1.0 if r.temperature_air > temp_high else 0.0

        if r.soil_moisture is not None and sm_low is not None:
            r.water_stress_flag = 1.0 if r.soil_moisture < sm_low else 0.0

        # ── Quality score: válidos / (válidos + inválidos) ──
        present = sum(1 for f in SENSOR_FIELDS if getattr(r, f, None) is not None)
        invalid = len(r.invalid_fields)
        if present + invalid > 0:
            r.quality_score = round(present / (present + invalid), 4)
        else:
            r.quality_score = 1.0

        return r
