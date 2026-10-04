import pytest
from skyfield.api import load

from satrx.tracking.passes import TrajectoryPoint, compute_trajectory, find_passes, interpolate_azel
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


def _make_traj(*points: tuple[float, float, float]) -> list[TrajectoryPoint]:
    return [TrajectoryPoint(seconds_from_start=s, azimuth_deg=az, elevation_deg=el) for s, az, el in points]


class TestInterpolateAzel:

    def test_nominal_midpoint(self) -> None:
        traj = _make_traj((0.0, 10.0, 20.0), (100.0, 50.0, 40.0))
        az, el = interpolate_azel(traj, 50.0)
        assert az == pytest.approx(30.0, abs=0.01)
        assert el == pytest.approx(30.0, abs=0.01)

    def test_clamp_before_start(self) -> None:
        traj = _make_traj((10.0, 90.0, 5.0), (100.0, 180.0, 30.0))
        az, el = interpolate_azel(traj, 0.0)
        assert az == pytest.approx(90.0)
        assert el == pytest.approx(5.0)

    def test_clamp_after_end(self) -> None:
        traj = _make_traj((0.0, 90.0, 5.0), (100.0, 180.0, 30.0))
        az, el = interpolate_azel(traj, 999.0)
        assert az == pytest.approx(180.0)
        assert el == pytest.approx(30.0)

    def test_azimuth_wrap_350_to_10(self) -> None:
        # le chemin le plus court de 350 a 10 passe par 0 (delta +20, pas -340)
        traj = _make_traj((0.0, 350.0, 10.0), (100.0, 10.0, 30.0))
        az, el = interpolate_azel(traj, 50.0)
        # mi-chemin : 350 + 0.5 * (+20) = 360 % 360 = 0
        assert az == pytest.approx(0.0, abs=0.5)

    def test_empty_trajectory_raises(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            interpolate_azel([], 50.0)

    def test_exact_boundary_point(self) -> None:
        traj = _make_traj((0.0, 45.0, 10.0), (200.0, 135.0, 60.0), (400.0, 270.0, 5.0))
        az, el = interpolate_azel(traj, 200.0)
        assert az == pytest.approx(135.0, abs=0.01)
        assert el == pytest.approx(60.0, abs=0.01)

    def test_interop_with_compute_trajectory(self) -> None:
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        start = ts.utc(2024, 3, 20)
        traj = compute_trajectory(satellite, PARIS, start, duration_s=600.0, n_samples=20)
        # l'interpolation a t=300 doit etre dans les bornes physiques
        az, el = interpolate_azel(traj, 300.0)
        assert 0.0 <= az < 360.0
        assert -90.0 <= el <= 90.0
