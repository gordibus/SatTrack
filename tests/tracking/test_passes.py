import pytest
from skyfield.api import load

from satrx.tracking.passes import find_passes
from satrx.tracking.station import GroundStation
from satrx.tracking.tle import load_satellite

ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"

PARIS = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)


@pytest.fixture
def iss():
    ts = load.timescale()
    return load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2), ts


class TestFindPasses:

    def test_nominal_case(self, iss):
        satellite, ts = iss
        start = ts.utc(2024, 3, 20)
        end = ts.utc(2024, 3, 21)

        passes = find_passes(satellite, PARIS, start, end, min_elevation_deg=10.0)

        assert len(passes) >= 1
        first = passes[0]
        assert start.tt < first.rise_time.tt < first.culminate_time.tt < first.set_time.tt < end.tt
        assert first.max_elevation_deg >= 10.0

    def test_edge_case_end_before_start(self, iss):
        satellite, ts = iss
        start = ts.utc(2024, 3, 21)
        end = ts.utc(2024, 3, 20)

        with pytest.raises(ValueError):
            find_passes(satellite, PARIS, start, end)

    def test_edge_case_invalid_min_elevation(self, iss):
        satellite, ts = iss
        start = ts.utc(2024, 3, 20)
        end = ts.utc(2024, 3, 21)

        with pytest.raises(ValueError):
            find_passes(satellite, PARIS, start, end, min_elevation_deg=95.0)

    def test_interop_higher_min_elevation_yields_fewer_or_equal_passes(self, iss):
        satellite, ts = iss
        start = ts.utc(2024, 3, 20)
        end = ts.utc(2024, 3, 22)

        low = find_passes(satellite, PARIS, start, end, min_elevation_deg=5.0)
        high = find_passes(satellite, PARIS, start, end, min_elevation_deg=40.0)

        assert len(high) <= len(low)
        assert all(p.max_elevation_deg >= 40.0 for p in high)
