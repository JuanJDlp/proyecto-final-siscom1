# Umbrales agroclimáticos y constantes agronómicas por cultivo.
# Fuente: fase_1/analisis_eda.md §7.1 (caña de azúcar) y §7.2 (palma de aceite)
# Contexto local: Valle del Cauca, Colombia.
#
# Estructura por variable: {"low": float|None, "high": float|None, "unit": str}
#   low / high = límites de alerta agronómicos. None = sin límite en esa dirección.

THRESHOLDS = {
    "sugarcane": {
        "temperature_air":    {"low": 18.0,  "high": 35.0,   "unit": "°C"},
        "rainfall":           {"low": 900.0, "high": 1900.0, "unit": "mm/mes"},
        "humidity":           {"low": 55.0,  "high": 88.0,   "unit": "%"},
        "soil_ph":            {"low": 5.5,   "high": 8.5,    "unit": "pH"},
        "soil_moisture":      {"low": 15.0,  "high": 40.0,   "unit": "%"},
        "solar_radiation":    {"low": 12.0,  "high": 28.0,   "unit": "MJ/m²/d"},
        "wind_speed":         {"low": None,  "high": 40.0,   "unit": "km/h"},
        "evapotranspiration": {"low": None,  "high": 9.0,    "unit": "mm/d"},
        "vpd":                {"low": None,  "high": 3.0,    "unit": "kPa"},
        "disease_risk":       {"low": None,  "high": 0.70,   "unit": "score"},
        "irrigation_need":    {"low": None,  "high": 0.60,   "unit": "score"},
    },
    "oil_palm": {
        "temperature_air":    {"low": 18.0,  "high": 35.0,   "unit": "°C"},
        "rainfall":           {"low": 150.0, "high": 250.0,  "unit": "mm/mes"},
        "humidity":           {"low": 60.0,  "high": None,   "unit": "%"},
        "soil_ph":            {"low": 4.0,   "high": 7.0,    "unit": "pH"},
        "soil_moisture":      {"low": 30.0,  "high": 80.0,   "unit": "%"},
        "solar_radiation":    {"low": 15.0,  "high": 30.0,   "unit": "MJ/m²/d"},
        "wind_speed":         {"low": None,  "high": 25.2,   "unit": "km/h"},
        "evapotranspiration": {"low": None,  "high": 9.0,    "unit": "mm/d"},
        "vpd":                {"low": None,  "high": 2.5,    "unit": "kPa"},
        "disease_risk":       {"low": None,  "high": 0.70,   "unit": "score"},
        "irrigation_need":    {"low": None,  "high": 0.60,   "unit": "score"},
    },
}

# Rangos físicos absolutos de los sensores (fuera de estos rangos = lectura inválida)
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

# Constantes agronómicas por cultivo.
#   Tbase:  temperatura base para Growing Degree Days (GDD).
#   Kc:     coeficiente de cultivo FAO-56 para fase de máximo desarrollo.
#   Topt:   temperatura óptima del cultivo (centro del rango ideal).
CROP_CONSTANTS = {
    "sugarcane": {
        "Tbase": 18.0,   # caña — Inman-Bamber, 1994
        "Kc":    1.25,   # FAO-56 mid-season para caña en suelo bien regado
        "Topt":  27.0,
    },
    "oil_palm": {
        "Tbase": 15.0,   # palma — Corley & Tinker, 2016
        "Kc":    1.00,   # FAO-56 promedio anual para palma adulta
        "Topt":  28.0,
    },
}
