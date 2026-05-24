import logging
from typing import List

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config.settings import Settings
from models.sensor_reading import AlertEvent, SensorReading

log = logging.getLogger("influx_writer")

# Variables crudas que escribimos al bucket de raw data tal como llegan.
RAW_FIELDS = [
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed",
]

# Variables (crudas + derivadas) que se escriben en el bucket procesado.
PROCESSED_FIELDS = RAW_FIELDS + [
    "evapotranspiration", "crop_water_requirement", "water_balance",
    "vpd", "dew_point", "thi", "heat_index",
    "gdd_increment", "disease_risk", "irrigation_need",
    "heat_stress_index", "water_stress_flag", "quality_score",
]


class InfluxWriter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = InfluxDBClient(
            url=settings.influx_url,
            token=settings.influx_token,
            org=settings.influx_org,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self._ensure_buckets()

    def _ensure_buckets(self):
        buckets_api = self.client.buckets_api()
        org = self.settings.influx_org

        for bucket_name, retention_seconds in [
            (self.settings.influx_bucket_processed, 0),
            (self.settings.influx_bucket_alerts, 30 * 24 * 3600),
        ]:
            existing = buckets_api.find_bucket_by_name(bucket_name)
            if existing is None:
                buckets_api.create_bucket(
                    bucket_name=bucket_name, org=org,
                    retention_rules=[
                        {"type": "expire", "everySeconds": retention_seconds,
                         "shardGroupDurationSeconds": 0}
                    ] if retention_seconds > 0 else [],
                )
                log.info("Bucket '%s' creado.", bucket_name)
            else:
                log.info("Bucket '%s' ya existe.", bucket_name)

    def _base_point(self, reading: SensorReading) -> Point:
        p = (
            Point("sensor_data")
            .tag("parcela", reading.parcela)
            .tag("cultivo", reading.cultivo)
            .time(reading.timestamp, WritePrecision.NS)
        )
        if reading.area_ha is not None:
            p = p.field("area_ha", float(reading.area_ha))
        return p

    def write_raw(self, reading: SensorReading):
        point = self._base_point(reading)
        for f in RAW_FIELDS:
            value = getattr(reading, f, None)
            if value is not None:
                point = point.field(f, value)
        self.write_api.write(bucket=self.settings.influx_bucket_raw, record=point)

    def write_processed(self, reading: SensorReading):
        point = self._base_point(reading)
        for f in PROCESSED_FIELDS:
            value = getattr(reading, f, None)
            if value is not None:
                point = point.field(f, float(value))
        self.write_api.write(bucket=self.settings.influx_bucket_processed, record=point)

    def write_alerts(self, alerts: List[AlertEvent]):
        for alert in alerts:
            point = (
                Point("alert_events")
                .tag("parcela", alert.parcela)
                .tag("cultivo", alert.cultivo)
                .tag("variable", alert.variable)
                .tag("severity", alert.severity)
                .tag("threshold_type", alert.threshold_type)
                .field("value", alert.value)
                .field("threshold_value", alert.threshold_value)
                .time(alert.timestamp, WritePrecision.NS)
            )
            self.write_api.write(bucket=self.settings.influx_bucket_alerts, record=point)

    def close(self):
        self.write_api.close()
        self.client.close()
