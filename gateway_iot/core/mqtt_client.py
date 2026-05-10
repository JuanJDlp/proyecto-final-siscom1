import logging
import time

import paho.mqtt.client as mqtt

from config.settings import Settings
from core.pipeline import DataPipeline

log = logging.getLogger("mqtt_client")


class MQTTClient:
    def __init__(self, settings: Settings, pipeline: DataPipeline):
        self.settings = settings
        self.pipeline = pipeline
        self.client = mqtt.Client(client_id="iot_gateway_agro_v2", protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Conectado al broker MQTT %s:%d", self.settings.mqtt_broker, self.settings.mqtt_port)
            client.subscribe(self.settings.mqtt_topic, qos=1)
            log.info("Suscrito a topic: %s", self.settings.mqtt_topic)
        else:
            log.error("Error de conexión MQTT rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning("Desconexión inesperada del broker MQTT (rc=%d)", rc)

    def _on_message(self, client, userdata, msg):
        try:
            self.pipeline.process(msg.payload)
        except Exception as exc:
            log.error("Error en on_message: %s", exc, exc_info=True)

    def _connect_with_retry(self, max_retries: int = 15) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                self.client.connect(
                    self.settings.mqtt_broker,
                    self.settings.mqtt_port,
                    keepalive=60,
                )
                return True
            except Exception as exc:
                log.warning("Intento %d/%d — broker no disponible: %s", attempt, max_retries, exc)
                if attempt < max_retries:
                    time.sleep(3)
        return False

    def start_loop(self):
        if not self._connect_with_retry():
            log.error("No se pudo conectar al broker MQTT. Abortando.")
            return
        log.info("Gateway iniciado — escuchando mensajes MQTT…")
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            log.info("Señal de interrupción — deteniendo gateway…")
        finally:
            self.client.disconnect()
