FROM python:3.11-slim

LABEL description="Simulador IoT Agrícola — Fase 2 — ICESI Sistemas y Comunicaciones I"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py .

ENV MQTT_BROKER=mosquitto
ENV MQTT_PORT=1883
ENV DATASET_PATH=/app/datasets/sugarcane-prediction-dataset.csv

CMD ["python", "simulator.py"]
