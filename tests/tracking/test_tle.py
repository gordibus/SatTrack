import pytest

from satrx.tracking.tle import load_satellite, parse_tle_text

# TLE reel (ISS ZARYA), fige a une epoque donnee : sert de fixture stable pour les tests,
# pas de fetch reseau necessaire pour valider le parsing/chargement.
ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"
ISS_TLE_3LE = f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}\n"


class TestParseTleText:

    def test_nominal_case(self):
        name, line1, line2 = parse_tle_text(ISS_TLE_3LE)
        assert name == ISS_NAME
        assert line1 == ISS_LINE1
        assert line2 == ISS_LINE2

    def test_nominal_case_two_line_format_without_name(self):
        name, line1, line2 = parse_tle_text(f"{ISS_LINE1}\n{ISS_LINE2}\n")
        assert name == "UNKNOWN"
        assert line1 == ISS_LINE1
        assert line2 == ISS_LINE2

    def test_edge_case_invalid_input(self):
        with pytest.raises(ValueError):
            parse_tle_text("une seule ligne")

    def test_edge_case_malformed_lines(self):
        with pytest.raises(ValueError):
            parse_tle_text(f"{ISS_NAME}\nligne pas du tout un TLE\nautre ligne invalide\n")

    def test_interop_with_load_satellite(self):
        name, line1, line2 = parse_tle_text(ISS_TLE_3LE)
        satellite = load_satellite(name, line1, line2)
        assert satellite.name == ISS_NAME
        assert satellite.model.satnum == 25544
