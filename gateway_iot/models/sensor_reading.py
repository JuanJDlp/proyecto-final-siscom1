from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SensorReading:
    # Identidad
    timestamp: datetime
    parcela: str
    cultivo: str
    area_ha: float

    # Variables crudas (provenientes del sensor / dataset)
    temperature_air: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    soil_ph: Optional[float] = None
    soil_moisture: Optional[float] = None
    solar_radiation: Optional[float] = None
    wind_speed: Optional[float] = None
    invalid_fields: List[str] = field(default_factory=list)

    # Variables derivadas (calculadas por DataEnricher)
    #   evapotranspiration: ahora CALCULADA en el gateway (FAO Jensen-Haise)
    evapotranspiration: Optional[float] = None        # mm/día (ETo)
    crop_water_requirement: Optional[float] = None    # mm/día (ETc = ETo·Kc)
    water_balance: Optional[float] = None             # mm/día (lluvia diaria − ETc)
    vpd: Optional[float] = None                       # kPa
    dew_point: Optional[float] = None                 # °C
    thi: Optional[float] = None                       # Temperature-Humidity Index
    heat_index: Optional[float] = None                # 0–1 continuo
    gdd_increment: Optional[float] = None             # °C·día por lectura
    disease_risk: Optional[float] = None              # 0–1
    irrigation_need: Optional[float] = None           # 0–1

    # Flags binarios (compatibilidad con alert_rules iniciales)
    heat_stress_index: float = 0.0                    # 0 / 1
    water_stress_flag: float = 0.0                    # 0 / 1

    # Calidad de datos
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
