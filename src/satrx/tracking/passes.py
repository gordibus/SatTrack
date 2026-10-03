from __future__ import annotations

from dataclasses import dataclass

from skyfield.api import EarthSatellite, wgs84
from skyfield.timelib import Time
from skyfield.toposlib import GeographicPosition

from satrx.tracking.station import GroundStation

_RISE, _CULMINATE, _SET = 0, 1, 2


@dataclass(frozen=True)
class SatellitePass:
    rise_time: Time
    culminate_time: Time
    set_time: Time
    max_elevation_deg: float


@dataclass(frozen=True)
class TrajectoryPoint:
    seconds_from_start: float
    elevation_deg: float
    azimuth_deg: float


def station_topos(station: GroundStation) -> GeographicPosition:
    return wgs84.latlon(
        station.latitude_deg, station.longitude_deg, elevation_m=station.elevation_m
    )


def find_passes(
    satellite: EarthSatellite,
    station: GroundStation,
    start: Time,
    end: Time,
    min_elevation_deg: float = 10.0,
) -> list[SatellitePass]:
    if end.tt <= start.tt:
        raise ValueError("end doit etre posterieur a start")
    if not 0.0 <= min_elevation_deg < 90.0:
        raise ValueError(f"min_elevation_deg doit etre dans [0, 90), recu {min_elevation_deg}")

    topos = station_topos(station)
    times, events = satellite.find_events(topos, start, end, altitude_degrees=min_elevation_deg)

    passes: list[SatellitePass] = []
    pending: dict[str, Time] = {}
    for t, event in zip(times, events):
        if event == _RISE:
            pending = {"rise": t}
        elif event == _CULMINATE and "rise" in pending:
            pending["culminate"] = t
        elif event == _SET and "rise" in pending and "culminate" in pending:
            pending["set"] = t
            elevation, _azimuth, _distance = (satellite - topos).at(pending["culminate"]).altaz()
            passes.append(
                SatellitePass(
                    rise_time=pending["rise"],
                    culminate_time=pending["culminate"],
                    set_time=pending["set"],
                    max_elevation_deg=elevation.degrees,
                )
            )
            pending = {}
    return passes


def compute_trajectory(
    satellite: EarthSatellite,
    station: GroundStation,
    start: Time,
    duration_s: float,
    n_samples: int = 100,
) -> list[TrajectoryPoint]:
    if duration_s <= 0.0:
        raise ValueError(f"duration_s doit etre positif, recu {duration_s}")
    if n_samples < 2:
        raise ValueError(f"n_samples doit etre >= 2, recu {n_samples}")

    topos = station_topos(station)
    ts = start.ts
    points: list[TrajectoryPoint] = []
    for i in range(n_samples):
        elapsed_s = duration_s * i / (n_samples - 1)
        t = ts.tt_jd(start.tt + elapsed_s / 86400.0)
        elevation, azimuth, _distance = (satellite - topos).at(t).altaz()
        points.append(
            TrajectoryPoint(
                seconds_from_start=elapsed_s,
                elevation_deg=elevation.degrees,
                azimuth_deg=azimuth.degrees,
            )
        )
    return points
