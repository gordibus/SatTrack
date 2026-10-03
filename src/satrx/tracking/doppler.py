from __future__ import annotations

from skyfield.api import EarthSatellite
from skyfield.timelib import Time

from satrx.tracking.passes import station_topos
from satrx.tracking.station import GroundStation

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0

_RANGE_RATE_HALF_WINDOW_S = 0.5


def _slant_range_km(satellite: EarthSatellite, station: GroundStation, t: Time) -> float:
    topos = station_topos(station)
    _elevation, _azimuth, distance = (satellite - topos).at(t).altaz()
    return float(distance.km)


def range_rate_m_per_s(satellite: EarthSatellite, station: GroundStation, t: Time) -> float:
    ts = t.ts
    dt_days = _RANGE_RATE_HALF_WINDOW_S / 86400.0
    t_before = ts.tt_jd(t.tt - dt_days)
    t_after = ts.tt_jd(t.tt + dt_days)

    range_before_km = _slant_range_km(satellite, station, t_before)
    range_after_km = _slant_range_km(satellite, station, t_after)

    range_rate_km_s = (range_after_km - range_before_km) / (2 * _RANGE_RATE_HALF_WINDOW_S)
    return range_rate_km_s * 1000.0


def doppler_shift_hz(
    satellite: EarthSatellite,
    station: GroundStation,
    t: Time,
    tx_freq_hz: float,
) -> float:
    if tx_freq_hz <= 0.0:
        raise ValueError(f"tx_freq_hz doit etre positive, recu {tx_freq_hz}")

    rate_m_s = range_rate_m_per_s(satellite, station, t)
    return -(rate_m_s / SPEED_OF_LIGHT_M_PER_S) * tx_freq_hz


def corrected_rx_freq_hz(
    satellite: EarthSatellite,
    station: GroundStation,
    t: Time,
    tx_freq_hz: float,
) -> float:
    return tx_freq_hz + doppler_shift_hz(satellite, station, t, tx_freq_hz)
