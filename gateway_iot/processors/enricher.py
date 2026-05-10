from config.thresholds import THRESHOLDS
from models.sensor_reading import SensorReading

SENSOR_FIELDS = [
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed", "evapotranspiration",
]


class DataEnricher:
    def enrich(self, reading: SensorReading) -> SensorReading:
        thresholds = THRESHOLDS.get(reading.cultivo, {})

        # heat_stress_index
        temp_thresh = thresholds.get("temperature_air", {})
        temp_high = temp_thresh.get("high")
        if reading.temperature_air is not None and temp_high is not None:
            reading.heat_stress_index = 1.0 if reading.temperature_air > temp_high else 0.0

        # water_stress_flag
        moisture_thresh = thresholds.get("soil_moisture", {})
        moisture_low = moisture_thresh.get("low")
        if reading.soil_moisture is not None and moisture_low is not None:
            reading.water_stress_flag = 1.0 if reading.soil_moisture < moisture_low else 0.0

        # quality_score: campos válidos / campos con valor presente
        present = sum(
            1 for f in SENSOR_FIELDS if getattr(reading, f, None) is not None
        )
        invalid = len(reading.invalid_fields)
        if present + invalid > 0:
            reading.quality_score = round(present / (present + invalid), 4)
        else:
            reading.quality_score = 1.0

        return reading
