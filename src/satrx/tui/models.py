from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class FavoriteEntry:
    norad_id: int
    name: str

    def to_dict(self) -> dict[str, object]:
        return {"norad_id": self.norad_id, "name": self.name}

    @staticmethod
    def from_dict(d: dict[str, object]) -> "FavoriteEntry":
        return FavoriteEntry(norad_id=int(str(d["norad_id"])), name=str(d["name"]))


@dataclass
class ScheduledTask:
    task_id: str
    satellite_name: str
    norad_id: int
    start_utc: datetime
    duration_s: float
    center_freq_hz: float
    sample_rate_hz: float
    lna_gain_db: Optional[float]
    vga_gain_db: Optional[float]
    amplifier: bool
    status: str = "attente"   # attente | en_cours | termine | annule
    output_file: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "satellite_name": self.satellite_name,
            "norad_id": self.norad_id,
            "start_utc": self.start_utc.isoformat(),
            "duration_s": self.duration_s,
            "center_freq_hz": self.center_freq_hz,
            "sample_rate_hz": self.sample_rate_hz,
            "lna_gain_db": self.lna_gain_db,
            "vga_gain_db": self.vga_gain_db,
            "amplifier": self.amplifier,
            "status": self.status,
            "output_file": self.output_file,
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> "ScheduledTask":
        dt = datetime.fromisoformat(str(d["start_utc"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        lna = d.get("lna_gain_db")
        vga = d.get("vga_gain_db")
        of = d.get("output_file")
        return ScheduledTask(
            task_id=str(d["task_id"]),
            satellite_name=str(d["satellite_name"]),
            norad_id=int(str(d["norad_id"])),
            start_utc=dt,
            duration_s=float(str(d["duration_s"])),
            center_freq_hz=float(str(d["center_freq_hz"])),
            sample_rate_hz=float(str(d["sample_rate_hz"])),
            lna_gain_db=float(str(lna)) if lna is not None else None,
            vga_gain_db=float(str(vga)) if vga is not None else None,
            amplifier=bool(d.get("amplifier", False)),
            status=str(d.get("status", "attente")),
            output_file=str(of) if of is not None else None,
        )

    @property
    def seconds_until_start(self) -> float:
        return (self.start_utc - datetime.now(timezone.utc)).total_seconds()


@dataclass
class AppConfig:
    station_name: str = "Paris-Nord"
    latitude_deg: float = 48.910178
    longitude_deg: float = 2.254915
    elevation_m: float = 50.0
    default_lna_gain_db: float = 32.0
    default_vga_gain_db: float = 30.0
    default_amplifier: bool = False
    default_sample_rate_msps: float = 2.048
    ppm_correction: int = 300
    tle_refresh_hours: int = 24
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    rotator_port: str = ""   # port serie EXOS-II, vide = pas de rotateur

    def to_dict(self) -> dict[str, object]:
        return {
            "station_name": self.station_name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "elevation_m": self.elevation_m,
            "default_lna_gain_db": self.default_lna_gain_db,
            "default_vga_gain_db": self.default_vga_gain_db,
            "default_amplifier": self.default_amplifier,
            "default_sample_rate_msps": self.default_sample_rate_msps,
            "ppm_correction": self.ppm_correction,
            "tle_refresh_hours": self.tle_refresh_hours,
            "raw_dir": self.raw_dir,
            "processed_dir": self.processed_dir,
            "rotator_port": self.rotator_port,
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> "AppConfig":
        cfg = AppConfig()
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


@dataclass
class PassInfo:
    satellite_name: str
    norad_id: int
    aos_utc: datetime
    los_utc: datetime
    max_elevation_deg: float
    is_favorite: bool = False

    @property
    def duration_s(self) -> float:
        return (self.los_utc - self.aos_utc).total_seconds()

    @property
    def seconds_until_aos(self) -> float:
        return (self.aos_utc - datetime.now(timezone.utc)).total_seconds()

    @property
    def elevation_label(self) -> str:
        if self.max_elevation_deg >= 50.0:
            return "BON"
        if self.max_elevation_deg >= 20.0:
            return "MOY"
        return "BAS"

    @property
    def elevation_symbol(self) -> str:
        if self.max_elevation_deg >= 50.0:
            return "◆"
        if self.max_elevation_deg >= 20.0:
            return "◇"
        return "·"


def load_favorites(path: Path) -> list[FavoriteEntry]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [FavoriteEntry.from_dict(d) for d in data]
    except Exception:
        return []


def save_favorites(path: Path, favorites: list[FavoriteEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([f.to_dict() for f in favorites], indent=2))


def load_scheduled_tasks(path: Path) -> list[ScheduledTask]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [ScheduledTask.from_dict(d) for d in data]
    except Exception:
        return []


def save_scheduled_tasks(path: Path, tasks: list[ScheduledTask]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([t.to_dict() for t in tasks], indent=2))


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text())
        return AppConfig.from_dict(data)
    except Exception:
        return AppConfig()


def save_config(path: Path, cfg: AppConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg.to_dict(), indent=2))


# Known satellites with their NORAD IDs for quick lookup
KNOWN_SATELLITES: list[FavoriteEntry] = [
    FavoriteEntry(57166, "METEOR-M2 3"),
    FavoriteEntry(40069, "METEOR-M2 2"),
    FavoriteEntry(28654, "NOAA 18"),
    FavoriteEntry(33591, "NOAA 19"),
    FavoriteEntry(25338, "NOAA 15"),
    FavoriteEntry(25544, "ISS (ZARYA)"),
    FavoriteEntry(43249, "METEOR-M2 4"),
]
