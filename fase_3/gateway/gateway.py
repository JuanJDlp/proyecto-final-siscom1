#!/usr/bin/env python3
"""
Fase 3 — Gateway IoT Agrícola
Universidad ICESI — Sistemas y Comunicaciones I — Mayo 2026

Rol: Edge Computing Gateway
  - Suscribe al Broker MQTT (Mosquitto)
  - Recibe mensajes JSON de los 4 sensores simulados
  - Valida y transforma cada mensaje
  - Escribe en InfluxDB como serie temporal

Pipeline:
  Broker MQTT → on_message() → validar → Point InfluxDB → write_api.write()
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gateway")

# ─── Configuración desde variables de entorno ─────────────────────────────────
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC  = os.environ.get("MQTT_TOPIC", "agricultura/sensores/#")

INFLUX_URL    = os.environ.get("INFLUX_URL",    "http://localhost:8086")
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "agro-iot-token-fase3-icesi-2026")
INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "agricultura")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "agro_iot_data")

# ─── Campos de sensores válidos ───────────────────────────────────────────────
# Solo estos campos se almacenan como fields en InfluxDB.
# Todos los demás keys del payload se ignoran.
SENSOR_FIELDS = {
    "temperature_air",
    "humidity",
    "rainfall",
    "soil_ph",
    "soil_moisture",
    "solar_radiation",
    "wind_speed",
    "evapotranspiration",
}

# ─── Cliente InfluxDB ─────────────────────────────────────────────────────────
influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def parse_timestamp(ts_str: str) -> datetime:
    """
    Convierte el timestamp del payload "YYYY-MM-DD HH:MM:SS" a datetime UTC.
    Si falla el parseo, usa el timestamp actual como fallback.
    """
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        log.warning("Timestamp inválido '%s' — usando tiempo actual", ts_str)
        return datetime.now(tz=timezone.utc)


def build_point(payload: dict) -> Point | None:
    """
    Construye un influxdb_client.Point desde el payload JSON del sensor.

    Retorna None si el payload no tiene los campos obligatorios o
    si no contiene ningún field de sensor válido.

    Estructura del Point resultante:
      measurement: sensor_data
      tags:        parcela, cultivo, area_ha
      fields:      los sensores presentes en este tick (payload parcial OK)
      timestamp:   derivado de payload["timestamp"]
    """
    # Validar campos obligatorios
    for required in ("parcela", "cultivo", "timestamp"):
        if not payload.get(required):
            log.warning("Campo obligatorio '%s' faltante: %s", required, payload)
            return None

    # Extraer solo los fields de sensores presentes en este payload
    fields = {}
    for sensor in SENSOR_FIELDS:
        value = payload.get(sensor)
        if value is not None:
            try:
                fields[sensor] = float(value)
            except (ValueError, TypeError):
                log.warning("Valor no numérico en '%s': %s", sensor, value)

    if not fields:
        log.warning("Payload sin campos de sensor válidos: %s", payload)
        return None

    # Construir el Point
    ts = parse_timestamp(payload["timestamp"])

    point = (
        Point("sensor_data")
        .tag("parcela", payload["parcela"])
        .tag("cultivo", payload["cultivo"])
        .tag("area_ha", str(payload.get("area_ha", "")))
        .time(ts, WritePrecision.NS)
    )

    for field_name, field_value in fields.items():
        point = point.field(field_name, field_value)

    return point


def on_connect(client, userdata, flags, rc):
    """Callback al conectar al broker MQTT."""
    if rc == 0:
        log.info("✔ Conectado al broker MQTT %s:%d", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPIC, qos=1)
        log.info("Suscrito a topic: %s", MQTT_TOPIC)
    else:
        log.error("✘ Error de conexión MQTT rc=%d", rc)


def on_disconnect(client, userdata, rc):
    """Callback al desconectarse del broker."""
    if rc != 0:
        log.warning("Desconexión inesperada del broker MQTT (rc=%d) — reconectando…", rc)


def on_message(client, userdata, msg):
    """
    Callback principal: se ejecuta por cada mensaje MQTT recibido.

    Flujo:
      1. Decodificar bytes → string UTF-8
      2. Parsear JSON → dict
      3. Construir Point de InfluxDB
      4. Escribir en bucket
    """
    try:
        # 1. Decodificar
        raw = msg.payload.decode("utf-8")

        # 2. Parsear JSON
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error("JSON inválido en topic '%s': %s | raw: %s", msg.topic, e, raw[:200])
            return

        # 3. Construir Point
        point = build_point(payload)
        if point is None:
            return

        # 4. Escribir en InfluxDB
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        # Log resumido para no saturar la consola
        fields_presentes = [f for f in SENSOR_FIELDS if f in payload]
        log.info(
            "[%s] %s → InfluxDB | campos=%s",
            payload.get("parcela", "?"),
            payload.get("cultivo", "?"),
            fields_presentes,
        )

    except Exception as e:
        log.error("Error procesando mensaje de '%s': %s", msg.topic, e, exc_info=True)


def connect_with_retry(client: mqtt.Client, max_retries: int = 15) -> bool:
    """Intenta conectar al broker MQTT con reintentos."""
    for attempt in range(1, max_retries + 1):
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            return True
        except Exception as exc:
            log.warning("Intento %d/%d — broker no disponible: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(3)
    return False


def main():
    log.info("=" * 60)
    log.info("  Gateway IoT Agrícola — Fase 3")
    log.info("  Universidad ICESI — Sistemas y Comunicaciones I")
    log.info("=" * 60)
    log.info("MQTT  : %s:%d → topic %s", MQTT_BROKER, MQTT_PORT, MQTT_TOPIC)
    log.info("InfluxDB: %s | org=%s | bucket=%s", INFLUX_URL, INFLUX_ORG, INFLUX_BUCKET)

    # Configurar cliente MQTT
    client = mqtt.Client(client_id="iot_gateway_agro", protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    # Conectar al broker con reintentos
    if not connect_with_retry(client):
        log.error("No se pudo conectar al broker MQTT después de varios intentos. Abortando.")
        return

    log.info("Gateway iniciado — escuchando mensajes MQTT…")

    try:
        # loop_forever() bloquea e invoca los callbacks automáticamente
        # También maneja reconexiones automáticas si el broker se cae
        client.loop_forever()
    except KeyboardInterrupt:
        log.info("Señal de interrupción — deteniendo gateway…")
    finally:
        client.disconnect()
        write_api.close()
        influx_client.close()
        log.info("Gateway detenido correctamente.")


if __name__ == "__main__":
    main()
