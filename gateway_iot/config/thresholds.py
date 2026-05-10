# Umbrales agroclimáticos por cultivo.
# Fuente: fase_1/analisis_eda.md §7.1 (caña de azúcar) y §7.2 (palma de aceite)
# low/high = límites de alerta; None = sin límite en esa dirección.

THRESHOLDS = {
    "sugarcane": {
        "temperature_air":    {"low": 18.0,  "high": 38.0,   "unit": "°C"},
        "rainfall":           {"low": 900.0,  "high": 1900.0, "unit": "mm/mes"},
        "humidity":           {"low": 55.0,  "high": 88.0,   "unit": "%"},
        "soil_ph":            {"low": 5.5,   "high": 8.5,    "unit": "pH"},
        "soil_moisture":      {"low": 15.0,  "high": 40.0,   "unit": "%"},
        "solar_radiation":    {"low": 12.0,  "high": 28.0,   "unit": "MJ/m²/d"},
        "wind_speed":         {"low": None,  "high": 40.0,   "unit": "km/h"},
        "evapotranspiration": {"low": None,  "high": 9.0,    "unit": "mm/d"},
    },
    "oil_palm": {
        "temperature_air": {"low": 18.0,  "high": 38.0,  "unit": "°C"},
        "humidity":        {"low": 60.0,  "high": None,  "unit": "%"},
        "soil_ph":         {"low": 4.0,   "high": 7.0,   "unit": "pH"},
        "wind_speed":      {"low": None,  "high": 25.2,  "unit": "km/h"},
    },
}

# Rangos físicos absolutos para validación (fuera de estos rangos = dato inválido del sensor)
PHYSICAL_RANGES = {
    "temperature_air":    (-10.0, 60.0),
    "humidity":           (0.0,   100.0),
    "rainfall":           (0.0,   5000.0),
    "soil_ph":            (0.0,   14.0),
    "soil_moisture":      (0.0,   100.0),
    "solar_radiation":    (0.0,   50.0),
    "wind_speed":         (0.0,   200.0),
    "evapotranspiration": (0.0,   30.0),
}
