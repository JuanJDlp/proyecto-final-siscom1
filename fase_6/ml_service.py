#!/usr/bin/env python3
"""
Fase 6 — Servicio de Predicción de Series de Tiempo IoT
Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026

Para cada parcela y cada variable agroclimática:
  1. Toma los últimos 20 valores reales desde InfluxDB (ventana deslizante)
  2. Ajusta una regresión lineal sobre esa ventana (modelo liviano, robusto con pocos puntos)
  3. Proyecta 3 pasos adelante (~5 minutos con lecturas cada ~90s)
  4. Escribe los valores predichos en agro_iot_ml con tag type=predicted
  5. Re-escribe el último valor real con tag type=real para comparación en Grafana

¿Por qué regresión lineal sobre ventana deslizante?
  - Con ~20 puntos, ARIMA requiere ajuste de parámetros complejo y es inestable
  - Ridge/Lasso sobre features temporales (t, t², rolling_mean) da predicciones
    suaves y bien calibradas para horizontes cortos (5 min)
  - Es interpretable: la pendiente indica si la variable está subiendo o bajando
"""

import os
import time
import logging
import numpy as np
from datetime import datetime, timezone, timedelta

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from sklearn.linear_model import Ridge

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-14s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ml_service")

# ── Config desde entorno ──────────────────────────────────────────────────────
INFLUX_URL   = os.environ.get("INFLUX_URL",   "http://influxdb:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "agro-iot-token-fase3-icesi-2026")
INFLUX_ORG   = os.environ.get("INFLUX_ORG",   "agricultura")
BUCKET_IN    = os.environ.get("INFLUX_BUCKET_PROCESSED", "agro_iot_processed")
BUCKET_OUT   = os.environ.get("INFLUX_BUCKET_ML",        "agro_iot_ml")
INTERVAL     = int(os.environ.get("PREDICTION_INTERVAL", "30"))   # segundos entre ciclos
WINDOW_SIZE  = int(os.environ.get("WINDOW_SIZE",          "20"))  # puntos históricos
STEPS_AHEAD  = int(os.environ.get("STEPS_AHEAD",           "3"))  # pasos a predecir (~5 min)

PARCELAS = ["parcela_1", "parcela_2", "parcela_3", "parcela_4"]

# Todas las variables + metadatos de display
VARIABLES = {
    "temperature_air":    {"unit": "°C",       "label": "Temperatura del Aire"},
    "humidity":           {"unit": "%",        "label": "Humedad Relativa"},
    "rainfall":           {"unit": "mm",       "label": "Precipitación"},
    "soil_ph":            {"unit": "pH",       "label": "pH del Suelo"},
    "soil_moisture":      {"unit": "%",        "label": "Humedad del Suelo"},
    "solar_radiation":    {"unit": "MJ/m²/d",  "label": "Radiación Solar"},
    "wind_speed":         {"unit": "km/h",     "label": "Velocidad del Viento"},
    "evapotranspiration": {"unit": "mm/día",   "label": "Evapotranspiración"},
}


# ── Modelo de predicción: Ridge sobre features temporales ────────────────────

def predict_next_steps(values: list[float], steps_ahead: int) -> list[float]:
    """
    Dado un array de valores históricos, predice los próximos `steps_ahead` valores.

    Features usadas:
      - t          (índice temporal lineal — captura tendencia)
      - t²         (curvatura suave)
      - rolling_3  (media móvil últimos 3 — reduce ruido del sensor)

    Retorna una lista de `steps_ahead` predicciones.
    Garantiza que los valores predichos estén dentro de ±3σ del histórico
    para no mostrar predicciones absurdas en Grafana.
    """
    n = len(values)
    if n < 5:
        # No hay suficientes puntos — repetir último valor
        return [values[-1]] * steps_ahead

    arr = np.array(values, dtype=float)
    t   = np.arange(n)

    # Rolling mean con ventana 3
    rolling = np.convolve(arr, np.ones(3)/3, mode='same')

    X = np.column_stack([t, t**2, rolling])
    y = arr

    model = Ridge(alpha=1.0)
    model.fit(X, y)

    # Proyectar features para los próximos steps
    predictions = []
    last_vals = list(arr[-3:])  # últimos 3 para rolling

    for step in range(1, steps_ahead + 1):
        t_next     = n - 1 + step
        roll_next  = np.mean(last_vals[-3:])
        x_next     = np.array([[t_next, t_next**2, roll_next]])
        pred       = float(model.predict(x_next)[0])

        # Clamp a ±3σ del histórico para no disparar valores absurdos
        mu, sigma = arr.mean(), arr.std()
        if sigma > 0:
            pred = np.clip(pred, mu - 3*sigma, mu + 3*sigma)

        predictions.append(round(pred, 4))
        last_vals.append(pred)

    return predictions


# ── Lectura de InfluxDB ───────────────────────────────────────────────────────

def query_window(client: InfluxDBClient, parcela: str, field: str) -> list[tuple]:
    """
    Retorna los últimos WINDOW_SIZE valores de `field` para `parcela`
    como lista de (timestamp_utc, value) ordenada cronológicamente.
    """
    query = f"""
from(bucket: "{BUCKET_IN}")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.parcela == "{parcela}")
  |> filter(fn: (r) => r._field == "{field}")
  |> sort(columns: ["_time"], desc: false)
  |> tail(n: {WINDOW_SIZE})
"""
    tables = client.query_api().query(query, org=INFLUX_ORG)
    result = []
    for table in tables:
        for record in table.records:
            result.append((record.get_time(), float(record.get_value())))
    return result


def query_cultivo(client: InfluxDBClient, parcela: str) -> str:
    query = f"""
from(bucket: "{BUCKET_IN}")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.parcela == "{parcela}")
  |> last()
"""
    tables = client.query_api().query(query, org=INFLUX_ORG)
    for table in tables:
        for record in table.records:
            cultivo = record.values.get("cultivo")
            if cultivo:
                return cultivo
    return "unknown"


# ── Escritura en InfluxDB ─────────────────────────────────────────────────────

def write_predictions(write_api, parcela: str, cultivo: str,
                      field: str, last_ts: datetime,
                      real_value: float, predictions: list[float],
                      avg_interval_s: float):
    """
    Escribe:
      - 1 punto con type=real  (el último valor medido, re-publicado en bucket ML)
      - N puntos con type=predicted (uno por cada step futuro)
    """
    # Punto real
    point_real = (
        Point("sensor_forecast")
        .tag("parcela",   parcela)
        .tag("cultivo",   cultivo)
        .tag("variable",  field)
        .tag("type",      "real")
        .field("value",   real_value)
        .time(last_ts, WritePrecision.NS)
    )
    write_api.write(bucket=BUCKET_OUT, record=point_real)

    # Puntos predichos — cada uno `avg_interval_s` segundos en el futuro
    for i, pred_val in enumerate(predictions, start=1):
        future_ts = last_ts + timedelta(seconds=avg_interval_s * i)
        point_pred = (
            Point("sensor_forecast")
            .tag("parcela",  parcela)
            .tag("cultivo",  cultivo)
            .tag("variable", field)
            .tag("type",     "predicted")
            .field("value",  pred_val)
            .time(future_ts, WritePrecision.NS)
        )
        write_api.write(bucket=BUCKET_OUT, record=point_pred)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def ensure_bucket(client: InfluxDBClient):
    api = client.buckets_api()
    if api.find_bucket_by_name(BUCKET_OUT) is None:
        api.create_bucket(bucket_name=BUCKET_OUT, org=INFLUX_ORG)
        log.info("Bucket '%s' creado.", BUCKET_OUT)
    else:
        log.info("Bucket '%s' ya existe.", BUCKET_OUT)


def connect_influx() -> InfluxDBClient:
    for attempt in range(1, 20):
        try:
            client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
            client.ping()
            log.info("✔ Conectado a InfluxDB (%s)", INFLUX_URL)
            return client
        except Exception as exc:
            log.warning("Intento %d/19 — InfluxDB no disponible: %s", attempt, exc)
            time.sleep(5)
    raise RuntimeError("No se pudo conectar a InfluxDB después de 19 intentos.")


# ── Loop principal ────────────────────────────────────────────────────────────

def main():
    log.info("=" * 62)
    log.info("  Fase 6 — Predicción de Variables Agroclimáticas")
    log.info("  Variables: %d | Parcelas: %d | Horizonte: %d pasos (~5 min)",
             len(VARIABLES), len(PARCELAS), STEPS_AHEAD)
    log.info("=" * 62)

    client    = connect_influx()
    ensure_bucket(client)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    log.info("Esperando datos iniciales del simulador (60s)...")
    time.sleep(60)
    log.info("Iniciando ciclo de predicción cada %ds.", INTERVAL)

    while True:
        cycle_start = time.time()
        ok = 0

        for parcela in PARCELAS:
            cultivo = query_cultivo(client, parcela)

            for field in VARIABLES:
                try:
                    window = query_window(client, parcela, field)

                    if len(window) < 5:
                        log.debug("[%s/%s] Solo %d puntos — esperando más datos.",
                                  parcela, field, len(window))
                        continue

                    timestamps = [ts for ts, _ in window]
                    values     = [v  for _, v  in window]

                    # Calcular intervalo promedio entre lecturas
                    if len(timestamps) > 1:
                        deltas = [(timestamps[i+1] - timestamps[i]).total_seconds()
                                  for i in range(len(timestamps)-1)]
                        avg_interval = np.mean(deltas)
                    else:
                        avg_interval = 90.0  # fallback: 90 segundos

                    predictions = predict_next_steps(values, STEPS_AHEAD)
                    last_ts     = timestamps[-1]
                    real_value  = values[-1]

                    write_predictions(
                        write_api, parcela, cultivo, field,
                        last_ts, real_value, predictions, avg_interval,
                    )
                    ok += 1

                    log.debug("[%s/%s] real=%.3f → pred=%s",
                              parcela, field, real_value,
                              [f"{p:.2f}" for p in predictions])

                except Exception as exc:
                    log.error("[%s/%s] Error: %s", parcela, field, exc)

        elapsed = time.time() - cycle_start
        total   = len(PARCELAS) * len(VARIABLES)
        log.info("Ciclo OK — %d/%d predicciones escritas — %.1fs", ok, total, elapsed)
        time.sleep(max(0, INTERVAL - elapsed))


if __name__ == "__main__":
    main()