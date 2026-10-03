import pytest
from skyfield.api import load

from satrx.tracking.doppler import corrected_rx_freq_hz, doppler_shift_hz, range_rate_m_per_s
from satrx.tracking.passes import find_passes
from satrx.tracking.station import GroundStation
from satrx.tracking.tle import load_satellite

ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"
PARIS = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)

LRPT_FREQ_HZ = 137.0e6

# Vitesse orbitale LEO ~7.8 km/s : la vitesse radiale ne peut jamais depasser cette borne,
# ce qui plafonne le decalage Doppler possible pour une frequence donnee.
MAX_PLAUSIBLE_SHIFT_HZ = (7_800.0 / 299_792_458.0) * LRPT_FREQ_HZ


@pytest.fixture
def iss_first_pass():
    ts = load.timescale()
    satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
    start = ts.utc(2024, 3, 20)
    end = ts.utc(2024, 3, 21)
    passes = find_passes(satellite, PARIS, start, end, min_elevation_deg=10.0)
    return satellite, passes[0]


class TestDopplerShiftHz:

    def test_nominal_case_approaching_satellite_gives_positive_shift(self, iss_first_pass):
        satellite, sat_pass = iss_first_pass

        shift_at_rise = doppler_shift_hz(satellite, PARIS, sat_pass.rise_time, LRPT_FREQ_HZ)

        assert 0.0 < shift_at_rise < MAX_PLAUSIBLE_SHIFT_HZ

    def test_nominal_case_receding_satellite_gives_negative_shift(self, iss_first_pass):
        satellite, sat_pass = iss_first_pass

        shift_at_set = doppler_shift_hz(satellite, PARIS, sat_pass.set_time, LRPT_FREQ_HZ)

        assert -MAX_PLAUSIBLE_SHIFT_HZ < shift_at_set < 0.0

    def test_edge_case_non_positive_frequency(self, iss_first_pass):
        satellite, sat_pass = iss_first_pass

        with pytest.raises(ValueError):
            doppler_shift_hz(satellite, PARIS, sat_pass.rise_time, 0.0)

    def test_interop_corrected_rx_freq_matches_shift(self, iss_first_pass):
        satellite, sat_pass = iss_first_pass

        shift = doppler_shift_hz(satellite, PARIS, sat_pass.rise_time, LRPT_FREQ_HZ)
        corrected = corrected_rx_freq_hz(satellite, PARIS, sat_pass.rise_time, LRPT_FREQ_HZ)

        assert corrected == pytest.approx(LRPT_FREQ_HZ + shift)


class TestRangeRateMPerS:

    def test_nominal_case_sign_matches_shift_direction(self, iss_first_pass):
        satellite, sat_pass = iss_first_pass

        rate_at_rise = range_rate_m_per_s(satellite, PARIS, sat_pass.rise_time)
        rate_at_set = range_rate_m_per_s(satellite, PARIS, sat_pass.set_time)

        assert rate_at_rise < 0.0
        assert rate_at_set > 0.0
