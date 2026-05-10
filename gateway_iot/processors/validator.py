import json
import logging
from datetime import datetime, timezone

from config.thresholds import PHYSICAL_RANGES
from models.sensor_reading import SensorReading

log = logging.getLogger("validator")

SENSOR_FIELDS = [
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed", "evapotranspiration",
]


class DataValidator:
    def validate(self, payload: dict) -> SensorReading | None:
        for required in ("parcela", "cultivo", "timestamp"):
            if not payload.get(required):
                log.warning("Campo obligatorio '%s' faltante: %s", required, payload)
                return None

        try:
            ts = datetime.strptime(payload["timestamp"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            log.warning("Timestamp inválido '%s' — usando tiempo actual", payload.get("timestamp"))
            ts = datetime.now(tz=timezone.utc)

        invalid_fields: list[str] = []
        sensor_values: dict[str, float | None] = {}

        for field_name in SENSOR_FIELDS:
            raw = payload.get(field_name)
            if raw is None:
                sensor_values[field_name] = None
                continue
            try:
                value = float(raw)
            except (ValueError, TypeError):
                log.warning("Valor no numérico en '%s': %s", field_name, raw)
                invalid_fields.append(field_name)
                sensor_values[field_name] = None
                continue

            lo, hi = PHYSICAL_RANGES.get(field_name, (-float("inf"), float("inf")))
            if not (lo <= value <= hi):
                log.warning(
                    "Valor fuera de rango físico '%s'=%s [%s, %s]", field_name, value, lo, hi
                )
                invalid_fields.append(field_name)
                sensor_values[field_name] = None
            else:
                sensor_values[field_name] = value

        try:
            area_ha = float(payload.get("area_ha", 0.0))
        except (ValueError, TypeError):
            area_ha = 0.0

        return SensorReading(
            timestamp=ts,
            parcela=payload["parcela"],
            cultivo=payload["cultivo"],
            area_ha=area_ha,
            temperature_air=sensor_values.get("temperature_air"),
            humidity=sensor_values.get("humidity"),
            rainfall=sensor_values.get("rainfall"),
            soil_ph=sensor_values.get("soil_ph"),
            soil_moisture=sensor_values.get("soil_moisture"),
            solar_radiation=sensor_values.get("solar_radiation"),
            wind_speed=sensor_values.get("wind_speed"),
            evapotranspiration=sensor_values.get("evapotranspiration"),
            invalid_fields=invalid_fields,
        )
