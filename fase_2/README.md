# Fase 2 — Simulador de Sensores IoT Agrícolas

**Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026**

---

## Descripción

Simulador de sensores agrícolas que lee el dataset histórico de caña de azúcar
(`sugarcane-prediction-dataset.csv`, 3.000 filas) y publica lecturas en tiempo real
hacia un Broker MQTT (Eclipse Mosquitto). Simula 4 parcelas en hilos paralelos con
ruido gaussiano por sensor y ciclo continuo del dataset.

---

## Arquitectura

```
Dataset CSV
    │
    ▼
simulator.py ──publica──► Eclipse Mosquitto :1883
    │                           │
    │  4 hilos paralelos        ▼
    │  (una parcela/hilo)   topic: agricultura/sensores/<parcela>
    │
    ▼  (Fase 3)
Gateway IoT (Node-RED) → InfluxDB
```

---

## Parcelas simuladas

| Parcela    | Cultivo          | Área  | Sensores activos                                                |
|------------|------------------|-------|-----------------------------------------------------------------|
| parcela_1  | Caña de azúcar   | 5 ha  | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_2  | Caña de azúcar   | 3.5 ha | temperature_air, humidity, rainfall, wind_speed, evapotranspiration |
| parcela_3  | Palma de aceite  | 8 ha  | temperature_air, humidity, rainfall, soil_ph, soil_moisture, solar_radiation |
| parcela_4  | Palma de aceite  | 6.5 ha | temperature_air, humidity, rainfall, wind_speed                 |

---

## Frecuencias de envío

| Sensor               | Frecuencia | Real equivalente |
|----------------------|-----------|-----------------|
| temperature_air      | 15 s      | 15 min          |
| humidity             | 15 s      | 15 min          |
| wind_speed           | 15 s      | 15 min          |
| soil_moisture        | 30 s      | 30 min          |
| solar_radiation      | 30 s      | 30 min          |
| rainfall             | 60 s      | 1 hora          |
| soil_ph              | 60 s      | 2 horas         |
| evapotranspiration   | 60 s      | diaria          |

---

## Payload JSON (ejemplo)

```json
{
  "timestamp": "2026-05-03 14:30:00",
  "parcela": "parcela_1",
  "cultivo": "sugarcane",
  "area_ha": 5.0,
  "temperature_air": 28.47,
  "humidity": 70.83,
  "rainfall": 1462.5,
  "soil_ph": 7.21,
  "soil_moisture": 26.8,
  "solar_radiation": 22.34
}
```

---

## Cómo ejecutar

### Opción A — Docker Compose (recomendada)

```bash
# Desde la carpeta fase_2/
cd fase_2

# Construir e iniciar todos los servicios
docker compose up --build

# Ver solo los logs del simulador
docker compose logs -f simulator

# Detener
docker compose down
```

### Opción B — Ejecución local

**Requisitos:** Python 3.11+, Mosquitto corriendo en localhost:1883

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar simulador (el broker debe estar activo)
python simulator.py
```

**Para instalar Mosquitto localmente:**
```bash
# Ubuntu/Debian
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

---

## Verificar publicaciones (suscriptor de prueba)

Desde otra terminal, suscribirse a todos los topics de sensores:

```bash
# Ver todas las parcelas
mosquitto_sub -h localhost -p 1883 -t "agricultura/sensores/#" -v

# Ver solo parcela_3 (palma de aceite)
mosquitto_sub -h localhost -p 1883 -t "agricultura/sensores/parcela_3" -v

# Con docker compose activo
docker exec -it mqtt_broker mosquitto_sub -t "agricultura/sensores/#" -v
```

---

## Variables de entorno

| Variable       | Default                              | Descripción                      |
|----------------|--------------------------------------|----------------------------------|
| `MQTT_BROKER`  | `localhost`                          | Host del broker MQTT             |
| `MQTT_PORT`    | `1883`                               | Puerto del broker                |
| `DATASET_PATH` | `../datasets/sugarcane-prediction-dataset.csv` | Ruta al dataset CSV |

---

## Qué esperar

Al iniciar verás en los logs:

1. **Carga del dataset**: 3.000 filas reducidas a las 8 columnas de sensores
2. **Conexión al broker**: confirmación de conexión a Mosquitto
3. **4 líneas de inicio**: una por parcela mostrando cultivo, área y sensores
4. **Publicaciones periódicas**: cada 15 s muestra qué sensores dispararon y en qué fila

Ejemplo de log:
```
2026-05-03 14:30:00 [parcela_1   ] INFO — [parcela_1] tick=   0 row=   0 sensores_activos=['temperature_air', 'humidity', 'rainfall', 'soil_ph', 'soil_moisture', 'solar_radiation']
2026-05-03 14:30:15 [parcela_1   ] INFO — [parcela_1] tick=   1 row=   0 sensores_activos=['temperature_air', 'humidity']
2026-05-03 14:30:30 [parcela_1   ] INFO — [parcela_1] tick=   2 row=   0 sensores_activos=['temperature_air', 'humidity', 'soil_moisture', 'solar_radiation']
```

El dataset cicla indefinidamente: al llegar a la fila 3.000 vuelve a la fila 0.
Para las parcelas de palma de aceite, los valores son adaptados automáticamente
a sus rangos agronómicos (pH 4–6, humedad suelo 30–55%, temperatura −2.5°C, lluvia ×1.25).

---

## Notas para Fase 3

- **Topic base**: `agricultura/sensores/<parcela_id>`
- **QoS**: 1 (al menos una entrega garantizada)
- **Formato**: JSON UTF-8
- **Siguiente paso**: Node-RED suscribe a `agricultura/sensores/#`, valida/enriquece y escribe en InfluxDB
