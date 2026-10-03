import pytest
from skyfield.api import load

from satrx.acquisition.params import RecordingParams, duration_from_pass
from satrx.tracking.passes import SatellitePass, find_passes
from satrx.tracking.station import GroundStation
from satrx.tracking.tle import load_satellite

ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"
PARIS = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)


class TestRecordingParams:

    def test_nominal_case(self):
        params = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.1e6,
            sample_rate_hz=1.024e6,
            duration_s=600.0,
            gain_db=40.0,
        )
        assert params.center_freq_hz == pytest.approx(137.1e6)

    def test_nominal_case_without_gain(self):
        params = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.1e6,
            sample_rate_hz=1.024e6,
            duration_s=600.0,
        )
        assert params.gain_db is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"satellite_name": "  "},
            {"center_freq_hz": 0.0},
            {"sample_rate_hz": -1.0},
            {"duration_s": 0.0},
            {"gain_db": -5.0},
            {"lna_gain_db": -1.0},
        ],
    )
    def test_edge_case_invalid_input(self, kwargs):
        defaults = {
            "satellite_name": "METEOR-M2 3",
            "center_freq_hz": 137.1e6,
            "sample_rate_hz": 1.024e6,
            "duration_s": 600.0,
        }
        defaults.update(kwargs)
        with pytest.raises(ValueError):
            RecordingParams(**defaults)


class TestDurationFromPass:

    def test_nominal_case(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        passes = find_passes(
            satellite, PARIS, ts.utc(2024, 3, 20), ts.utc(2024, 3, 21), min_elevation_deg=10.0
        )
        sat_pass = passes[0]

        duration_s = duration_from_pass(sat_pass)

        assert 60.0 < duration_s < 1200.0

    def test_edge_case_set_before_rise(self):
        ts = load.timescale()
        t0 = ts.utc(2024, 3, 20, 10, 0, 0)
        t1 = ts.utc(2024, 3, 20, 9, 0, 0)
        invalid_pass = SatellitePass(
            rise_time=t0, culminate_time=t0, set_time=t1, max_elevation_deg=20.0
        )

        with pytest.raises(ValueError):
            duration_from_pass(invalid_pass)

    def test_interop_with_recording_params(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        passes = find_passes(
            satellite, PARIS, ts.utc(2024, 3, 20), ts.utc(2024, 3, 21), min_elevation_deg=10.0
        )
        sat_pass = passes[0]

        params = RecordingParams(
            satellite_name="ISS (ZARYA)",
            center_freq_hz=145.8e6,
            sample_rate_hz=1.024e6,
            duration_s=duration_from_pass(sat_pass),
        )

        assert params.duration_s == pytest.approx(
            (sat_pass.set_time.tt - sat_pass.rise_time.tt) * 86400.0
        )
