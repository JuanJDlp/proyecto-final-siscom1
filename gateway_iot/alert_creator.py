#!/usr/bin/env python3
"""
alert_creator.py — Generador de condiciones de alerta para el sistema IoT Agrícola
Universidad ICESI · Sistemas y Comunicaciones I · Mayo 2026

Publica mensajes MQTT con valores extremos que disparan TODAS las reglas de alerta
definidas en grafana/provisioning/alerting/alert_rules.yaml.

El flujo es:
  Este script → MQTT → Gateway IoT → InfluxDB (agro_iot_alerts) → Grafana → Email

Uso:
    # Requiere que el stack esté corriendo:  docker compose up -d
    pip install paho-mqtt

    python alert_creator.py                          # todos los escenarios, una ronda
    python alert_creator.py --loop                   # ciclo continuo hasta Ctrl+C
    python alert_creator.py --scenario heat          # solo estrés calórico
    python alert_creator.py --scenario water         # solo estrés hídrico
    python alert_creator.py --scenario wind          # solo viento fuerte
    python alert_creator.py --scenario humidity      # solo humedad baja
    python alert_creator.py --scenario quality       # solo calidad de datos baja
    python alert_creator.py --broker 192.168.1.5     # broker en IP remota
    python alert_creator.py --interval 10            # espera 10 s entre rondas (loop)
"""

import argparse
import json
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# ─── Colores ANSI ─────────────────────────────────────────────────────────────
R  = "\033[91m"   # rojo
Y  = "\033[93m"   # amarillo
G  = "\033[92m"   # verde
B  = "\033[94m"   # azul
C  = "\033[96m"   # cyan
W  = "\033[97m"   # blanco brillante
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

# ─── Configuración por defecto ────────────────────────────────────────────────
DEFAULT_BROKER = "localhost"
DEFAULT_PORT   = 1883
BASE_TOPIC     = "agricultura/sensores"


# ─── Definición de escenarios de alerta ──────────────────────────────────────

SCENARIOS = {

    # ── 1. Estrés calórico — temperatura muy por encima del umbral (38 °C) ────
    "heat": {
        "label": "Estres Calorico",
        "icon":  "🌡️",
        "color": R,
        "description": "Temperatura 44 °C (+15.8% sobre umbral 38 °C) → heat_stress_index=1 → WARNING",
        "messages": [
            {
                "parcela": "parcela_1", "cultivo": "sugarcane", "area_ha": 5.0,
                "temperature_air": 44.0,      # 38 * 1.158 → warning
                "humidity": 70.0,
                "rainfall": 1400.0,
                "soil_ph": 6.8,
                "soil_moisture": 28.0,
                "solar_radiation": 22.0,
            },
            {
                "parcela": "parcela_2", "cultivo": "sugarcane", "area_ha": 3.5,
                "temperature_air": 49.0,      # 38 * 1.29 → critical (>20%)
                "humidity": 68.0,
                "rainfall": 1350.0,
                "wind_speed": 8.0,
                "evapotranspiration": 5.0,
            },
            {
                "parcela": "parcela_3", "cultivo": "oil_palm", "area_ha": 8.0,
                "temperature_air": 46.0,      # critical para palma
                "humidity": 75.0,
                "rainfall": 1600.0,
                "soil_ph": 5.2,
                "soil_moisture": 55.0,
                "solar_radiation": 24.0,
            },
        ],
    },

    # ── 2. Estrés hídrico — soil_moisture bajo umbral mínimo (15%) ────────────
    "water": {
        "label": "Estres Hidrico",
        "icon":  "💧",
        "color": B,
        "description": "Humedad suelo 7 % (< 15 % umbral caña) → water_stress_flag=1 → CRITICAL",
        "messages": [
            {
                "parcela": "parcela_1", "cultivo": "sugarcane", "area_ha": 5.0,
                "temperature_air": 27.0,
                "humidity": 66.0,
                "rainfall": 1200.0,
                "soil_ph": 6.5,
                "soil_moisture": 7.0,         # 15 * (1 - 0.53) → critical
                "solar_radiation": 20.0,
            },
            {
                "parcela": "parcela_3", "cultivo": "oil_palm", "area_ha": 8.0,
                "temperature_air": 28.0,
                "humidity": 78.0,
                "rainfall": 1500.0,
                "soil_ph": 5.1,
                "soil_moisture": 12.0,        # bajo, activa flag
                "solar_radiation": 23.0,
            },
        ],
    },

    # ── 3. Humedad relativa baja ───────────────────────────────────────────────
    "humidity": {
        "label": "Humedad Baja",
        "icon":  "☁️",
        "color": C,
        "description": "Humedad 42 % palma (< 60 %) y 46 % caña (< 55 %) → WARNING",
        "messages": [
            {
                "parcela": "parcela_3", "cultivo": "oil_palm", "area_ha": 8.0,
                "temperature_air": 29.0,
                "humidity": 42.0,             # 60 * (1 - 0.30) → critical
                "rainfall": 1500.0,
                "soil_ph": 5.0,
                "soil_moisture": 48.0,
                "solar_radiation": 22.0,
            },
            {
                "parcela": "parcela_4", "cultivo": "oil_palm", "area_ha": 6.5,
                "temperature_air": 30.0,
                "humidity": 52.0,             # warning palma
                "rainfall": 1400.0,
                "wind_speed": 12.0,
            },
            {
                "parcela": "parcela_1", "cultivo": "sugarcane", "area_ha": 5.0,
                "temperature_air": 26.0,
                "humidity": 46.0,             # critical caña
                "rainfall": 1300.0,
                "soil_ph": 6.6,
                "soil_moisture": 26.0,
                "solar_radiation": 21.0,
            },
        ],
    },

    # ── 4. Viento fuerte — palma de aceite ────────────────────────────────────
    "wind": {
        "label": "Viento Fuerte",
        "icon":  "💨",
        "color": Y,
        "description": "Viento 35 km/h palma (> 25.2 km/h umbral) → CRITICAL",
        "messages": [
            {
                "parcela": "parcela_4", "cultivo": "oil_palm", "area_ha": 6.5,
                "temperature_air": 28.0,
                "humidity": 80.0,
                "rainfall": 1400.0,
                "wind_speed": 35.0,           # 25.2 * 1.39 → critical
            },
            {
                "parcela": "parcela_3", "cultivo": "oil_palm", "area_ha": 8.0,
                "temperature_air": 29.0,
                "humidity": 79.0,
                "rainfall": 1550.0,
                "soil_ph": 5.3,
                "soil_moisture": 50.0,
                "solar_radiation": 23.0,
            },
        ],
    },

    # ── 5. Calidad de datos baja — campos con valores inválidos ───────────────
    "quality": {
        "label": "Calidad Degradada",
        "icon":  "⚠️",
        "color": Y,
        "description": "Envía campos fuera de rango físico → quality_score < 0.5 → WARNING",
        "messages": [
            {
                "parcela": "parcela_2", "cultivo": "sugarcane", "area_ha": 3.5,
                "temperature_air": 27.0,
                "humidity": 9999.0,           # fuera de rango físico → inválido
                "rainfall": -500.0,           # fuera de rango físico → inválido
                "wind_speed": 9.0,
                "evapotranspiration": 5.5,
            },
            {
                "parcela": "parcela_4", "cultivo": "oil_palm", "area_ha": 6.5,
                "temperature_air": 200.0,     # fuera de rango físico → inválido
                "humidity": -10.0,            # fuera de rango físico → inválido
                "rainfall": 1400.0,
                "wind_speed": 11.0,
            },
        ],
    },
}


# ─── Cliente MQTT ─────────────────────────────────────────────────────────────

def build_client(broker: str, port: int) -> mqtt.Client:
    client = mqtt.Client(client_id="alert_creator", protocol=mqtt.MQTTv311)

    def on_connect(c, ud, flags, rc):
        if rc == 0:
            print(f"{G}✔ Conectado al broker MQTT {broker}:{port}{RST}")
        else:
            print(f"{R}✘ Error de conexión MQTT rc={rc}{RST}")
            sys.exit(1)

    def on_disconnect(c, ud, rc):
        if rc != 0:
            print(f"{Y}⚠ Desconectado del broker (rc={rc}){RST}")

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    return client


def connect(client: mqtt.Client, broker: str, port: int, retries: int = 10):
    for attempt in range(1, retries + 1):
        try:
            client.connect(broker, port, keepalive=60)
            client.loop_start()
            time.sleep(0.5)   # esperar callback on_connect
            return
        except Exception as exc:
            print(f"{Y}Intento {attempt}/{retries} — {exc}{RST}")
            if attempt == retries:
                print(f"{R}No se pudo conectar al broker. ¿Está corriendo docker compose up?{RST}")
                sys.exit(1)
            time.sleep(2)


# ─── Publicación ──────────────────────────────────────────────────────────────

def publish_message(client: mqtt.Client, parcela: str, payload: dict) -> None:
    payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    topic = f"{BASE_TOPIC}/{parcela}"
    msg   = json.dumps(payload, ensure_ascii=False)
    result = client.publish(topic, msg, qos=1)
    result.wait_for_publish()

    # Detectar qué violaciones se esperan
    violations = _detect_expected_violations(payload)

    print(
        f"  {DIM}→{RST} {W}{parcela}{RST} | "
        f"cultivo={payload.get('cultivo','?')} | "
        f"topic={topic}"
    )
    for sensor, value, expected in violations:
        print(f"    {R}⚡ {sensor}={value}  →  {expected}{RST}")
    if not violations:
        print(f"    {G}✓ Sin violaciones esperadas en este mensaje{RST}")


def _detect_expected_violations(payload: dict) -> list:
    """Analiza el payload y lista las violaciones esperadas según los umbrales."""
    cultivo = payload.get("cultivo", "")
    violations = []

    thresholds = {
        "sugarcane": {
            "temperature_air": (18.0, 38.0),
            "humidity":        (55.0, 88.0),
            "soil_moisture":   (15.0, 40.0),
            "wind_speed":      (None, 40.0),
            "rainfall":        (900.0, 1900.0),
            "soil_ph":         (5.5, 8.5),
            "solar_radiation": (12.0, 28.0),
            "evapotranspiration": (None, 9.0),
        },
        "oil_palm": {
            "temperature_air": (18.0, 38.0),
            "humidity":        (60.0, None),
            "soil_ph":         (4.0, 7.0),
            "wind_speed":      (None, 25.2),
        },
    }

    physical = {
        "temperature_air":    (-10.0, 60.0),
        "humidity":           (0.0,   100.0),
        "rainfall":           (0.0,   5000.0),
        "soil_moisture":      (0.0,   100.0),
        "wind_speed":         (0.0,   200.0),
        "solar_radiation":    (0.0,   50.0),
        "evapotranspiration": (0.0,   30.0),
        "soil_ph":            (0.0,   14.0),
    }

    crop_thresholds = thresholds.get(cultivo, {})

    for field, value in payload.items():
        if field in ("timestamp", "parcela", "cultivo", "area_ha"):
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue

        # Rango físico
        phys = physical.get(field)
        if phys and not (phys[0] <= v <= phys[1]):
            violations.append((field, v, f"FUERA DE RANGO FÍSICO [{phys[0]}, {phys[1]}] → quality↓"))
            continue

        # Umbral agronómico
        thresh = crop_thresholds.get(field)
        if thresh:
            lo, hi = thresh
            if lo is not None and v < lo:
                exceso = (lo - v) / lo * 100
                sev = "CRITICAL" if exceso > 20 else "WARNING"
                violations.append((field, v, f"{v} < {lo} → {sev} (déficit {exceso:.1f}%)"))
            elif hi is not None and v > hi:
                exceso = (v - hi) / hi * 100
                sev = "CRITICAL" if exceso > 20 else "WARNING"
                violations.append((field, v, f"{v} > {hi} → {sev} (exceso {exceso:.1f}%)"))

    return violations


# ─── Ejecución de escenarios ──────────────────────────────────────────────────

def run_scenario(client: mqtt.Client, name: str, scenario: dict, delay: float = 1.0) -> int:
    color = scenario["color"]
    print(f"\n{BOLD}{color}{'─'*60}{RST}")
    print(f"{BOLD}{color}  {scenario['icon']}  Escenario: {scenario['label']}{RST}")
    print(f"{color}  {scenario['description']}{RST}")
    print(f"{color}{'─'*60}{RST}")

    total = 0
    for msg in scenario["messages"]:
        parcela = msg.pop("parcela")
        publish_message(client, parcela, {**msg, "parcela": parcela})
        msg["parcela"] = parcela   # restaurar
        time.sleep(delay)
        total += 1

    print(f"  {G}✔ {total} mensaje(s) publicado(s){RST}")
    return total


def print_header():
    print(f"""
{BOLD}{W}╔══════════════════════════════════════════════════════════╗
║       GENERADOR DE ALERTAS — Sistema IoT Agrícola        ║
║       Universidad ICESI · Sistemas y Comunicaciones I    ║
╚══════════════════════════════════════════════════════════╝{RST}

{C}Propósito:{RST} Publicar valores extremos que disparen las reglas de alerta
           de Grafana y generen notificaciones por correo.

{C}Flujo:{RST}  alert_creator.py
           └─→ MQTT broker :1883
               └─→ Gateway IoT (pipeline)
                   └─→ InfluxDB agro_iot_alerts
                       └─→ Grafana (evalúa cada 1 min)
                           └─→ Email 📧
""")


def print_grafana_tip():
    print(f"""
{BOLD}{Y}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}
{BOLD}{Y}  Dónde ver las alertas:{RST}

  {W}Grafana  →{RST} http://localhost:3000  (admin / agro_grafana_2026)
              Alerting → Alert rules   (estado FIRING / PENDING)
              Alerting → Alert history (historial de disparos)

  {W}InfluxDB →{RST} http://localhost:8086  (admin / agro_admin_2026)
              Data Explorer → bucket {C}agro_iot_alerts{RST}
              measurement: alert_events
              query:  from(bucket: "agro_iot_alerts")
                        |> range(start: -10m)

  {W}Tiempo de evaluación Grafana:{RST}
    Las reglas evalúan cada {G}1 minuto{RST} y requieren la condición
    activa durante {G}2–5 minutos{RST} antes de pasar a FIRING.
    Sigue corriendo el script en modo {C}--loop{RST} para mantener los
    valores fuera de umbral el tiempo necesario.

  {W}Email:{RST} Revisa la bandeja (y SPAM) después de ~3 minutos
         si SMTP está configurado en grafana/grafana.ini [smtp].
{BOLD}{Y}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}
""")


# ─── Entry point ──────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Genera alertas agroclimáticas publicando valores extremos por MQTT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Escenarios disponibles:
  heat      → Temperatura extrema  (heat_stress_index = 1)
  water     → Humedad suelo baja   (water_stress_flag = 1)
  humidity  → Humedad relativa baja (palma < 60%, caña < 55%)
  wind      → Viento fuerte palma  (> 25.2 km/h)
  quality   → Datos degradados     (quality_score < 0.5)

Ejemplos:
  python alert_creator.py
  python alert_creator.py --loop --interval 30
  python alert_creator.py --scenario heat --loop
        """
    )
    p.add_argument("--broker",   default=DEFAULT_BROKER, help="Host del broker MQTT (default: localhost)")
    p.add_argument("--port",     default=DEFAULT_PORT, type=int, help="Puerto MQTT (default: 1883)")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys()), default=None,
                   help="Escenario específico (omitir = todos)")
    p.add_argument("--loop",     action="store_true",
                   help="Ciclo continuo — mantiene los valores extremos hasta Ctrl+C")
    p.add_argument("--interval", default=20, type=int,
                   help="Segundos entre rondas en modo --loop (default: 20)")
    p.add_argument("--delay",    default=0.8, type=float,
                   help="Segundos entre mensajes dentro de una ronda (default: 0.8)")
    return p.parse_args()


def main():
    args = parse_args()
    print_header()

    # Seleccionar escenarios a ejecutar
    if args.scenario:
        to_run = {args.scenario: SCENARIOS[args.scenario]}
    else:
        to_run = SCENARIOS

    # Conectar al broker
    print(f"{C}Conectando a broker MQTT {args.broker}:{args.port} ...{RST}")
    client = build_client(args.broker, args.port)
    connect(client, args.broker, args.port)

    print_grafana_tip()

    round_num = 0
    try:
        while True:
            round_num += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n{BOLD}{W}[Ronda {round_num}] {ts}{RST}")

            total_msgs = 0
            for name, scenario in to_run.items():
                total_msgs += run_scenario(client, name, scenario, delay=args.delay)

            print(f"\n{G}✔ Ronda {round_num} completada — {total_msgs} mensajes publicados{RST}")

            if not args.loop:
                print(f"\n{DIM}Tip: usa --loop para mantener los valores extremos hasta que Grafana dispare.{RST}")
                break

            print(f"\n{DIM}Próxima ronda en {args.interval} s ... (Ctrl+C para detener){RST}")
            for remaining in range(args.interval, 0, -1):
                print(f"\r  {DIM}⏳ {remaining:2d} s{RST}", end="", flush=True)
                time.sleep(1)
            print()

    except KeyboardInterrupt:
        print(f"\n\n{Y}⚠ Detenido por el usuario.{RST}")
        print(f"{DIM}Los valores extremos ya no se están publicando.")
        print(f"Las alertas FIRING en Grafana se resolverán en ~5 minutos.{RST}\n")
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"{G}✔ Desconectado del broker MQTT.{RST}")


if __name__ == "__main__":
    main()
