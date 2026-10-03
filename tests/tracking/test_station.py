import pytest

from satrx.tracking.station import GroundStation


class TestGroundStation:

    def test_nominal_case(self):
        station = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)
        assert station.name == "Paris"
        assert station.latitude_deg == pytest.approx(48.8566)
        assert station.elevation_m == pytest.approx(35.0)

    def test_edge_case_invalid_latitude(self):
        with pytest.raises(ValueError):
            GroundStation(name="Invalide", latitude_deg=91.0, longitude_deg=0.0)

    def test_edge_case_invalid_longitude(self):
        with pytest.raises(ValueError):
            GroundStation(name="Invalide", latitude_deg=0.0, longitude_deg=-181.0)
