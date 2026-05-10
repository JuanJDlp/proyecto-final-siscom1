#!/usr/bin/env python3
"""
Gateway IoT Agrícola — Fases 4, 5 y 7
Universidad ICESI — Sistemas y Comunicaciones I — Mayo 2026

Entry point: instancia y arranca el pipeline completo.
"""

import logging

from config.settings import Settings
from core.influx_writer import InfluxWriter
from core.mqtt_client import MQTTClient
from core.pipeline import DataPipeline
from processors.alert_checker import AlertChecker
from processors.enricher import DataEnricher
from processors.validator import DataValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("main")


def main():
    log.info("=" * 60)
    log.info("  Gateway IoT Agrícola — Fases 4 + 5 + 7")
    log.info("  Universidad ICESI — Sistemas y Comunicaciones I")
    log.info("=" * 60)

    settings = Settings()

    log.info("MQTT    : %s:%d → %s", settings.mqtt_broker, settings.mqtt_port, settings.mqtt_topic)
    log.info("InfluxDB: %s | org=%s", settings.influx_url, settings.influx_org)
    log.info("Buckets : raw=%s | processed=%s | alerts=%s",
             settings.influx_bucket_raw,
             settings.influx_bucket_processed,
             settings.influx_bucket_alerts)

    writer = InfluxWriter(settings)

    pipeline = DataPipeline(
        validator=DataValidator(),
        enricher=DataEnricher(),
        alert_checker=AlertChecker(),
        writer=writer,
    )

    mqtt_client = MQTTClient(settings=settings, pipeline=pipeline)

    try:
        mqtt_client.start_loop()
    finally:
        writer.close()
        log.info("Gateway detenido correctamente.")


if __name__ == "__main__":
    main()
