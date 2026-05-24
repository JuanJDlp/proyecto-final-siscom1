"""
AlertChecker — compara la lectura procesada contra los umbrales por cultivo
y emite eventos de alerta clasificados warning/critical.

Verifica tanto variables crudas como derivadas:
  · temperature_air, humidity, rainfall, soil_ph, soil_moisture,
    solar_radiation, wind_speed, evapotranspiration  (rangos agronómicos)
  · vpd                  (déficit de presión de vapor, > 3 kPa estrés severo)
  · disease_risk         (riesgo de enfermedad > 0.7 → alerta)
  · irrigation_need      (necesidad de riego > 0.6 → alerta)
"""

import logging
from typing import List

from config.thresholds import THRESHOLDS
from models.sensor_reading import AlertEvent, SensorReading

log = logging.getLogger("alert_checker")

CHECKED_FIELDS = [
    # Variables crudas
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed",
    # Variables derivadas con umbrales agronómicos
    "evapotranspiration", "vpd", "disease_risk", "irrigation_need",
]


class AlertChecker:
    def check(self, reading: SensorReading) -> List[AlertEvent]:
        alerts: List[AlertEvent] = []
        cultivo_thresholds = THRESHOLDS.get(reading.cultivo, {})

        for field_name in CHECKED_FIELDS:
            value = getattr(reading, field_name, None)
            if value is None:
                continue
            field_thresh = cultivo_thresholds.get(field_name)
            if field_thresh is None:
                continue

            low = field_thresh.get("low")
            high = field_thresh.get("high")

            if low is not None and value < low:
                excess_ratio = (low - value) / low if low != 0 else 0.0
                severity = "critical" if excess_ratio > 0.20 else "warning"
                alerts.append(AlertEvent(
                    timestamp=reading.timestamp,
                    parcela=reading.parcela,
                    cultivo=reading.cultivo,
                    variable=field_name,
                    value=value,
                    threshold_type="low",
                    threshold_value=low,
                    severity=severity,
                ))
                log.info(
                    "[alert] %s | %s | %s=%.2f < %.2f → %s",
                    reading.parcela, reading.cultivo, field_name, value, low,
                    severity.upper(),
                )

            elif high is not None and value > high:
                excess_ratio = (value - high) / high if high != 0 else 0.0
                severity = "critical" if excess_ratio > 0.20 else "warning"
                alerts.append(AlertEvent(
                    timestamp=reading.timestamp,
                    parcela=reading.parcela,
                    cultivo=reading.cultivo,
                    variable=field_name,
                    value=value,
                    threshold_type="high",
                    threshold_value=high,
                    severity=severity,
                ))
                log.info(
                    "[alert] %s | %s | %s=%.2f > %.2f → %s",
                    reading.parcela, reading.cultivo, field_name, value, high,
                    severity.upper(),
                )

        return alerts
