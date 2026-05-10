from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SensorReading:
    timestamp: datetime
    parcela: str
    cultivo: str
    area_ha: float
    temperature_air: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    soil_ph: Optional[float] = None
    soil_moisture: Optional[float] = None
    solar_radiation: Optional[float] = None
    wind_speed: Optional[float] = None
    evapotranspiration: Optional[float] = None
    invalid_fields: List[str] = field(default_factory=list)

    # Variables derivadas — calculadas por DataEnricher
    heat_stress_index: float = 0.0
    water_stress_flag: float = 0.0
    quality_score: float = 1.0


@dataclass
class AlertEvent:
    timestamp: datetime
    parcela: str
    cultivo: str
    variable: str
    value: float
    threshold_type: str   # "low" | "high"
    threshold_value: float
    severity: str          # "warning" | "critical"
