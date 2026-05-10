import os
from dataclasses import dataclass


@dataclass
class Settings:
    mqtt_broker: str = ""
    mqtt_port: int = 1883
    mqtt_topic: str = ""
    influx_url: str = ""
    influx_token: str = ""
    influx_org: str = ""
    influx_bucket_raw: str = ""
    influx_bucket_processed: str = ""
    influx_bucket_alerts: str = ""

    def __post_init__(self):
        self.mqtt_broker = os.environ.get("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
        self.mqtt_topic = os.environ.get("MQTT_TOPIC", "agricultura/sensores/#")
        self.influx_url = os.environ.get("INFLUX_URL", "http://localhost:8086")
        self.influx_token = os.environ.get("INFLUX_TOKEN", "agro-iot-token-fase3-icesi-2026")
        self.influx_org = os.environ.get("INFLUX_ORG", "agricultura")
        self.influx_bucket_raw = os.environ.get("INFLUX_BUCKET_RAW", "agro_iot_data")
        self.influx_bucket_processed = os.environ.get("INFLUX_BUCKET_PROCESSED", "agro_iot_processed")
        self.influx_bucket_alerts = os.environ.get("INFLUX_BUCKET_ALERTS", "agro_iot_alerts")
