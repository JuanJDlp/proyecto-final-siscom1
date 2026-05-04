#!/usr/bin/env python3
"""
Fase 2 — Simulador de Sensores IoT Agrícolas
Sistema de Monitoreo IoT y Analítica Agroclimática para Agricultura Digital
Universidad ICESI — Sistemas y Comunicaciones I — Mayo 2026

Fuentes de datos:
  Caña de azúcar  → sugarcane-prediction-dataset.csv  (datos reales de campo)
  Palma de aceite → crop-production-countries.csv      (temperatura + lluvia reales)
                    + distribuciones estadísticas EDA   (resto de variables)

Pipeline:
  Dataset histórico → Selección de variables → Lectura fila por fila
  → Simulación sensor IoT → 4 parcelas paralelas → Broker MQTT → Gateway IoT (Fase 3)
"""

import json
import os
import time
import threading
import logging
import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Dict, List, Optional

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-12s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("iot_simulator")

# ─── MQTT ─────────────────────────────────────────────────────────────────────
BROKER_HOST = os.environ.get("MQTT_BROKER", "localhost")
BROKER_PORT  = int(os.environ.get("MQTT_PORT", "1883"))
BASE_TOPIC   = "agricultura/sensores"

# ─── Rutas de datasets ────────────────────────────────────────────────────────
_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datasets")
SUGARCANE_PATH = os.environ.get(
    "SUGARCANE_PATH", os.path.join(_base, "sugarcane-prediction-dataset.csv")
)
PALM_PATH = os.environ.get(
    "PALM_PATH", os.path.join(_base, "crop-production-countries.csv")
)

# ─── Frecuencias de envío (segundos) ──────────────────────────────────────────
# Comprimidas para testing visual (real: 15 min / 30 min / 1–2 h)
BASE_TICK_S = 15

SENSOR_FREQ: Dict[str, int] = {
    "temperature_air":    15,   # Tier 1 — crítica
    "humidity":           15,   # Tier 1
    "wind_speed":         15,   # Tier 2
    "soil_moisture":      30,   # Tier 1 — mayor discriminador Q4 vs Q1 (+13.2%)
    "solar_radiation":    30,   # Tier 2
    "rainfall":           60,   # Tier 1
    "soil_ph":            60,   # Tier 1 — crítico para absorción de nutrientes
    "evapotranspiration": 60,   # Tier 2 — calculada en gateway
}

# ─── Mapeo caña: nombre IoT → columna dataset ─────────────────────────────────
SUGARCANE_COLUMN_MAP: Dict[str, str] = {
    "temperature_air":    "Temp_Avg_C",
    "humidity":           "Humidity_%",
    "rainfall":           "Rainfall_Total_mm",
    "soil_ph":            "Soil_pH",
    "soil_moisture":      "Soil_Moisture_%",
    "solar_radiation":    "Solar_Radiation_MJ_m2_day",
    "wind_speed":         "Wind_Speed_kmph",
    "evapotranspiration": "Evapotranspiration_mm_day",
}

# ─── Mapeo palma: variables disponibles en el dataset de países ───────────────
# El dataset de países solo tiene temperatura media anual y lluvia anual.
# El resto se genera con distribuciones estadísticas basadas en el EDA Fase 1.
PALM_COLUMN_MAP: Dict[str, str] = {
    "temperature_air": "avg_temperature_c",
    "rainfall":        "annual_rainfall_mm",
}

# ─── Distribuciones estadísticas para variables de palma sin dataset ──────────
# Parámetros obtenidos del EDA Fase 1 (sección 7.2 — Palma de aceite)
# Se usa proceso autorregresivo AR(1) para simular continuidad temporal del sensor.
PALM_DISTRIBUTIONS: Dict[str, dict] = {
    "humidity": {
        "mean": 80.0, "std": 5.0,
        "lo": 60.0,   "hi": 95.0,
    },
    "soil_ph": {
        "mean": 5.0,  "std": 0.35,
        "lo": 4.0,    "hi": 6.0,
    },
    "soil_moisture": {
        "mean": 42.0, "std": 6.0,
        "lo": 30.0,   "hi": 55.0,
    },
    "solar_radiation": {
        "mean": 22.0, "std": 3.0,
        "lo": 15.0,   "hi": 30.0,
    },
    "wind_speed": {
        "mean": 8.0,  "std": 2.0,
        "lo": 2.0,    "hi": 15.0,
    },
    "evapotranspiration": {
        "mean": 5.5,  "std": 1.0,
        "lo": 2.0,    "hi": 9.0,
    },
}

# Coeficiente AR(1): cuánto "recuerda" el sensor su valor anterior (0=sin memoria, 1=constante)
AR_ALPHA = 0.70

# ─── Ruido gaussiano — std por sensor (variabilidad de hardware real) ─────────
NOISE_STD: Dict[str, float] = {
    "temperature_air":    0.30,   # DHT22: spec ±0.5 °C
    "humidity":           0.50,   # DHT22: spec ±2 %
    "rainfall":          10.00,   # pluviómetro de cazoleta
    "soil_ph":            0.05,   # electrodo pH comercial
    "soil_moisture":      0.50,   # sensor capacitivo
    "solar_radiation":    0.30,   # piranómetro
    "wind_speed":         0.20,   # anemómetro de copa
    "evapotranspiration": 0.10,   # calculada — ruido bajo
}

# ─── Rangos válidos post-ruido por cultivo ────────────────────────────────────
RANGES_SUGARCANE: Dict[str, tuple] = {
    "temperature_air":    (10.0,   45.0),
    "humidity":           (50.0,   90.0),
    "rainfall":           (800.0,  2000.0),
    "soil_ph":            (6.0,    8.5),
    "soil_moisture":      (10.0,   40.0),
    "solar_radiation":    (15.0,   30.0),
    "wind_speed":         (2.0,    15.0),
    "evapotranspiration": (2.0,    8.0),
}

RANGES_PALM: Dict[str, tuple] = {
    "temperature_air":    (18.0,   35.0),
    "humidity":           (60.0,   95.0),
    "rainfall":           (1200.0, 2500.0),
    "soil_ph":            (4.0,    6.0),
    "soil_moisture":      (30.0,   55.0),
    "solar_radiation":    (15.0,   30.0),
    "wind_speed":         (2.0,    15.0),
    "evapotranspiration": (2.0,    9.0),
}

# ─── Definición de parcelas ───────────────────────────────────────────────────
PARCELAS: List[dict] = [
    {
        "id":       "parcela_1",
        "cultivo":  "sugarcane",
        "area_ha":  5.0,
        "sensores": ["temperature_air", "humidity", "rainfall",
                     "soil_ph", "soil_moisture", "solar_radiation"],
    },
    {
        "id":       "parcela_2",
        "cultivo":  "sugarcane",
        "area_ha":  3.5,
        "sensores": ["temperature_air", "humidity", "rainfall",
                     "wind_speed", "evapotranspiration"],
    },
    {
        "id":       "parcela_3",
        "cultivo":  "oil_palm",
        "area_ha":  8.0,
        "sensores": ["temperature_air", "humidity", "rainfall",
                     "soil_ph", "soil_moisture", "solar_radiation"],
    },
    {
        "id":       "parcela_4",
        "cultivo":  "oil_palm",
        "area_ha":  6.5,
        "sensores": ["temperature_air", "humidity", "rainfall", "wind_speed"],
    },
]


# ─── Carga de datasets ────────────────────────────────────────────────────────

def load_sugarcane(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = list(SUGARCANE_COLUMN_MAP.values())
    df = df[cols].dropna().reset_index(drop=True)
    log.info("Caña de azúcar: %d filas × %d sensores cargados", len(df), len(cols))
    return df


def load_palm(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    palm = df[df["crop_name"].str.lower().str.contains("palm", na=False)].copy()
    palm = palm[["avg_temperature_c", "annual_rainfall_mm"]].dropna().reset_index(drop=True)
    # Convertir lluvia anual → mensual aproximada (÷12) para mantener escala comparable
    palm["annual_rainfall_mm"] = palm["annual_rainfall_mm"] / 12.0
    log.info("Palma de aceite: %d filas reales (temperatura + lluvia mensual)", len(palm))
    return palm


# ─── Generador AR(1) para variables sintéticas de palma ──────────────────────

class ARSensor:
    """
    Genera valores continuos para un sensor usando un proceso AR(1):
      x_t = alpha * x_{t-1} + (1 - alpha) * sample_from_distribution
    Esto produce series temporales suaves y realistas, evitando saltos bruscos.
    """

    def __init__(self, sensor: str):
        dist = PALM_DISTRIBUTIONS[sensor]
        self.mean  = dist["mean"]
        self.std   = dist["std"]
        self.lo    = dist["lo"]
        self.hi    = dist["hi"]
        self.value = float(np.clip(np.random.normal(self.mean, self.std), self.lo, self.hi))

    def next(self) -> float:
        sample     = np.random.normal(self.mean, self.std)
        self.value = AR_ALPHA * self.value + (1.0 - AR_ALPHA) * sample
        return float(np.clip(self.value, self.lo, self.hi))


def apply_noise(sensor: str, value: float, crop: str) -> float:
    """Añade ruido gaussiano de hardware y recorta al rango válido del cultivo."""
    noisy  = value + np.random.normal(0.0, NOISE_STD.get(sensor, 0.0))
    ranges = RANGES_PALM if crop == "oil_palm" else RANGES_SUGARCANE
    lo, hi = ranges.get(sensor, (-np.inf, np.inf))
    return round(float(np.clip(noisy, lo, hi)), 4)


# ─── Simulador de parcela ─────────────────────────────────────────────────────

class ParcelaSimulator(threading.Thread):
    """
    Un hilo por parcela. Cicla el dataset indefinidamente y publica
    lecturas de sensores en MQTT con la frecuencia configurada.

    Caña (parcelas 1 & 2):
      - Todas las variables leídas de sugarcane-prediction-dataset.csv

    Palma (parcelas 3 & 4):
      - temperature_air, rainfall: leídas de crop-production-countries.csv (datos reales)
      - humidity, soil_ph, soil_moisture, solar_radiation, wind_speed, evapotranspiration:
        generadas por proceso AR(1) con distribuciones del EDA Fase 1
    """

    def __init__(
        self,
        config: dict,
        dataset: pd.DataFrame,
        client: mqtt.Client,
        start_row: int = 0,
    ):
        super().__init__(name=config["id"], daemon=True)
        self.cfg     = config
        self.dataset = dataset
        self.client  = client
        self.row_idx = start_row % len(dataset)
        self.tick    = 0
        self.topic   = f"{BASE_TOPIC}/{config['id']}"
        self.crop    = config["cultivo"]

        # Caché de último valor conocido → payload siempre completo
        self.last_value: Dict[str, float] = {}

        # Generadores AR(1) para variables sintéticas de palma
        self.ar_sensors: Dict[str, ARSensor] = {}
        if self.crop == "oil_palm":
            for sensor in config["sensores"]:
                if sensor not in PALM_COLUMN_MAP:
                    self.ar_sensors[sensor] = ARSensor(sensor)

    def _read_from_dataset(self, sensor: str, row: pd.Series) -> float:
        """Lee el valor crudo del dataset según el tipo de cultivo."""
        if self.crop == "sugarcane":
            col = SUGARCANE_COLUMN_MAP[sensor]
        else:
            col = PALM_COLUMN_MAP[sensor]
        return float(row[col])

    def _get_raw_value(self, sensor: str, row: pd.Series) -> float:
        """Obtiene el valor base del sensor: dataset (real) o AR(1) (sintético)."""
        if self.crop == "oil_palm" and sensor not in PALM_COLUMN_MAP:
            return self.ar_sensors[sensor].next()
        return self._read_from_dataset(sensor, row)

    def _should_fire(self, sensor: str) -> bool:
        freq      = SENSOR_FREQ.get(sensor, BASE_TICK_S)
        elapsed_s = self.tick * BASE_TICK_S
        return elapsed_s % freq == 0

    def _build_payload(self, row: pd.Series) -> dict:
        payload: dict = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parcela":   self.cfg["id"],
            "cultivo":   self.crop,
            "area_ha":   self.cfg["area_ha"],
        }
        for sensor in self.cfg["sensores"]:
            if self._should_fire(sensor):
                raw = self._get_raw_value(sensor, row)
                self.last_value[sensor] = apply_noise(sensor, raw, self.crop)
            if sensor in self.last_value:
                payload[sensor] = self.last_value[sensor]
        return payload

    def run(self):
        log.info(
            "▶  %s | cultivo=%-10s | área=%.1f ha | sensores=%s",
            self.cfg["id"], self.crop, self.cfg["area_ha"],
            ", ".join(self.cfg["sensores"]),
        )
        n = len(self.dataset)

        while True:
            row     = self.dataset.iloc[self.row_idx]
            payload = self._build_payload(row)
            msg     = json.dumps(payload, ensure_ascii=False)

            result = self.client.publish(self.topic, msg, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                fired = [s for s in self.cfg["sensores"] if self._should_fire(s)]
                log.info(
                    "[%s] tick=%4d row=%4d activos=%s",
                    self.cfg["id"], self.tick, self.row_idx, fired,
                )
            else:
                log.warning("[%s] Error MQTT rc=%d", self.cfg["id"], result.rc)

            # Avanzar fila cada 4 ticks (= 60 s, ciclo completo de frecuencias)
            if self.tick % 4 == 3:
                self.row_idx = (self.row_idx + 1) % n
                if self.row_idx == 0:
                    log.info("[%s] Dataset completado — reiniciando ciclo", self.cfg["id"])

            self.tick += 1
            time.sleep(BASE_TICK_S)


# ─── MQTT callbacks ───────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("✔ Conectado al broker MQTT %s:%d", BROKER_HOST, BROKER_PORT)
    else:
        log.error("✘ Error de conexión MQTT rc=%d", rc)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        log.warning("Desconexión inesperada del broker (rc=%d)", rc)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    log.info("=" * 65)
    log.info("  Simulador IoT Agrícola — Fase 2")
    log.info("  Universidad ICESI — Sistemas y Comunicaciones I")
    log.info("=" * 65)

    # 1. Cargar datasets por cultivo
    sugarcane_df = load_sugarcane(SUGARCANE_PATH)
    palm_df      = load_palm(PALM_PATH)

    # 2. Configurar y conectar cliente MQTT
    client = mqtt.Client(client_id="iot_agro_simulator", protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect

    log.info("Conectando a broker MQTT en %s:%d …", BROKER_HOST, BROKER_PORT)
    for attempt in range(1, 16):
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            break
        except Exception as exc:
            log.warning("Intento %d/15 — broker no disponible: %s", attempt, exc)
            if attempt == 15:
                log.error("No se pudo conectar al broker MQTT. Abortando.")
                return
            time.sleep(3)

    client.loop_start()

    # 3. Lanzar un hilo por parcela
    #    Caña → sugarcane_df | Palma → palm_df
    #    Offset inicial: cada parcela comienza en 1/4 diferente del dataset
    threads: List[ParcelaSimulator] = []
    for i, config in enumerate(PARCELAS):
        crop = config["cultivo"]
        if crop == "sugarcane":
            dataset = sugarcane_df
        else:
            dataset = palm_df

        offset = (i * len(dataset)) // len(PARCELAS)
        sim = ParcelaSimulator(config, dataset, client, start_row=offset)
        threads.append(sim)

    for t in threads:
        t.start()

    log.info("")
    log.info("Simulador activo — %d parcelas publicando en '%s/<parcela>'", len(threads), BASE_TOPIC)
    log.info("Fuentes: caña=sugarcane-prediction-dataset.csv | palma=crop-production-countries.csv + AR(1)")
    log.info("Presiona Ctrl+C para detener.")
    log.info("")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Deteniendo simulador…")
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Simulador detenido correctamente.")


if __name__ == "__main__":
    main()
