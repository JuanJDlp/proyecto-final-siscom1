import json
import logging

from core.influx_writer import InfluxWriter
from models.sensor_reading import SensorReading
from processors.alert_checker import AlertChecker
from processors.enricher import DataEnricher
from processors.validator import DataValidator

log = logging.getLogger("pipeline")


def _fmt(value):
    return f"{value:.2f}" if isinstance(value, (int, float)) else "—"


class DataPipeline:
    def __init__(
        self,
        validator: DataValidator,
        enricher: DataEnricher,
        alert_checker: AlertChecker,
        writer: InfluxWriter,
    ):
        self.validator = validator
        self.enricher = enricher
        self.alert_checker = alert_checker
        self.writer = writer

    def process(self, raw_payload: bytes):
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.error("Payload inválido: %s", exc)
            return

        reading: SensorReading | None = self.validator.validate(payload)
        if reading is None:
            return

        reading = self.enricher.enrich(reading)
        alerts = self.alert_checker.check(reading)

        try:
            self.writer.write_raw(reading)
            self.writer.write_processed(reading)
            if alerts:
                self.writer.write_alerts(alerts)
        except Exception as exc:
            log.error("Error escribiendo en InfluxDB: %s", exc, exc_info=True)
            return

        log.info(
            "[pipeline] %s | %s | T=%s°C HR=%s%% SM=%s%% | VPD=%s ETo=%s ETc=%s WB=%s | "
            "HI=%s GDD=%s disease=%s irrig=%s | Q=%.2f alerts=%d",
            reading.parcela, reading.cultivo,
            _fmt(reading.temperature_air),
            _fmt(reading.humidity),
            _fmt(reading.soil_moisture),
            _fmt(reading.vpd),
            _fmt(reading.evapotranspiration),
            _fmt(reading.crop_water_requirement),
            _fmt(reading.water_balance),
            _fmt(reading.heat_index),
            _fmt(reading.gdd_increment),
            _fmt(reading.disease_risk),
            _fmt(reading.irrigation_need),
            reading.quality_score,
            len(alerts),
        )
