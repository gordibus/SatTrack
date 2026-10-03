from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from satrx.tracking.passes import SatellitePass


class SdrDevice(str, Enum):
    RTL_SDR = "rtl_sdr"
    HACKRF = "hackrf_transfer"


@dataclass(frozen=True)
class RecordingParams:
    satellite_name: str
    center_freq_hz: float
    sample_rate_hz: float
    duration_s: float
    gain_db: float | None = None
    lna_gain_db: float | None = None
    amplifier_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.satellite_name.strip():
            raise ValueError("satellite_name ne doit pas etre vide")
        if self.center_freq_hz <= 0.0:
            raise ValueError(f"center_freq_hz doit etre positive, recu {self.center_freq_hz}")
        if self.sample_rate_hz <= 0.0:
            raise ValueError(f"sample_rate_hz doit etre positive, recu {self.sample_rate_hz}")
        if self.duration_s <= 0.0:
            raise ValueError(f"duration_s doit etre positive, recu {self.duration_s}")
        if self.gain_db is not None and self.gain_db < 0.0:
            raise ValueError(f"gain_db doit etre >= 0 si fourni, recu {self.gain_db}")
        if self.lna_gain_db is not None and self.lna_gain_db < 0.0:
            raise ValueError(f"lna_gain_db doit etre >= 0 si fourni, recu {self.lna_gain_db}")


def duration_from_pass(sat_pass: SatellitePass) -> float:
    duration_s = float(sat_pass.set_time.tt - sat_pass.rise_time.tt) * 86400.0
    if duration_s <= 0.0:
        raise ValueError("le passage fourni est invalide : set_time n'est pas posterieur a rise_time")
    return duration_s
