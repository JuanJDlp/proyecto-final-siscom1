import logging
from typing import List

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket import Bucket

from config.settings import Settings
from models.sensor_reading import AlertEvent, SensorReading

log = logging.getLogger("influx_writer")

SENSOR_FIELDS = [
    "temperature_air", "humidity", "rainfall", "soil_ph",
    "soil_moisture", "solar_radiation", "wind_speed", "evapotranspiration",
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
                buckets_api.create_bucket(bucket_name=bucket_name, org=org, retention_rules=[
                    {"type": "expire", "everySeconds": retention_seconds, "shardGroupDurationSeconds": 0}
                ] if retention_seconds > 0 else [])
                log.info("Bucket '%s' creado.", bucket_name)
            else:
                log.info("Bucket '%s' ya existe.", bucket_name)

    def write_raw(self, reading: SensorReading):
        point = (
            Point("sensor_data")
            .tag("parcela", reading.parcela)
            .tag("cultivo", reading.cultivo)
            .tag("area_ha", str(reading.area_ha))
            .time(reading.timestamp, WritePrecision.NS)
        )
        for field_name in SENSOR_FIELDS:
            value = getattr(reading, field_name, None)
            if value is not None:
                point = point.field(field_name, value)

        self.write_api.write(bucket=self.settings.influx_bucket_raw, record=point)

    def write_processed(self, reading: SensorReading):
        point = (
            Point("sensor_data")
            .tag("parcela", reading.parcela)
            .tag("cultivo", reading.cultivo)
            .tag("area_ha", str(reading.area_ha))
            .time(reading.timestamp, WritePrecision.NS)
        )
        for field_name in SENSOR_FIELDS:
            value = getattr(reading, field_name, None)
            if value is not None:
                point = point.field(field_name, value)

        point = point.field("heat_stress_index", reading.heat_stress_index)
        point = point.field("water_stress_flag", reading.water_stress_flag)
        point = point.field("quality_score", reading.quality_score)

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
