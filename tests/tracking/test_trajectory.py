import pytest
from skyfield.api import load

from satrx.tracking.passes import compute_trajectory, find_passes
from satrx.tracking.station import GroundStation
from satrx.tracking.tle import load_satellite

ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"
PARIS = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)


class TestComputeTrajectory:

    def test_nominal_case_length_and_bounds(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        start = ts.utc(2024, 3, 20)

        points = compute_trajectory(satellite, PARIS, start, duration_s=600.0, n_samples=10)

        assert len(points) == 10
        assert points[0].seconds_from_start == 0.0
        assert points[-1].seconds_from_start == pytest.approx(600.0)
        for p in points:
            assert -90.0 <= p.elevation_deg <= 90.0
            assert 0.0 <= p.azimuth_deg < 360.0

    def test_edge_case_invalid_duration(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        with pytest.raises(ValueError):
            compute_trajectory(satellite, PARIS, ts.utc(2024, 3, 20), duration_s=0.0)

    def test_edge_case_too_few_samples(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        with pytest.raises(ValueError):
            compute_trajectory(satellite, PARIS, ts.utc(2024, 3, 20), duration_s=100.0, n_samples=1)

    def test_interop_matches_find_passes_culmination(self):
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        start = ts.utc(2024, 3, 20)
        end = ts.utc(2024, 3, 21)
        sat_pass = find_passes(satellite, PARIS, start, end, min_elevation_deg=10.0)[0]

        duration_s = (sat_pass.set_time.tt - sat_pass.rise_time.tt) * 86400.0
        points = compute_trajectory(satellite, PARIS, sat_pass.rise_time, duration_s, n_samples=200)

        max_point = max(points, key=lambda p: p.elevation_deg)
        assert max_point.elevation_deg == pytest.approx(sat_pass.max_elevation_deg, abs=1.0)
