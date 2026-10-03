from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundStation:
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float = 0.0

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"latitude_deg doit etre dans [-90, 90], recu {self.latitude_deg}")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError(f"longitude_deg doit etre dans [-180, 180], recu {self.longitude_deg}")
