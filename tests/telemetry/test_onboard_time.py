import pytest

from satrx.telemetry.onboard_time import OnboardTime, parse_onboard_time


class TestParseOnboardTime:

    def test_nominal_case(self):
        data = bytes([14, 30, 45, 100])

        result = parse_onboard_time(data)

        assert result == OnboardTime(hours=14, minutes=30, seconds=45, milliseconds=400)

    def test_nominal_case_with_offset(self):
        data = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 14, 30, 45, 100])

        result = parse_onboard_time(data, offset=8)

        assert result == OnboardTime(hours=14, minutes=30, seconds=45, milliseconds=400)

    def test_edge_case_data_too_short(self):
        with pytest.raises(ValueError):
            parse_onboard_time(bytes([1, 2, 3]))

    def test_edge_case_invalid_hours(self):
        with pytest.raises(ValueError):
            parse_onboard_time(bytes([24, 0, 0, 0]))

    def test_edge_case_negative_offset(self):
        with pytest.raises(ValueError):
            parse_onboard_time(bytes([0, 0, 0, 0]), offset=-1)

    def test_interop_to_milliseconds_of_day(self):
        result = parse_onboard_time(bytes([1, 0, 0, 0]))

        assert result.to_milliseconds_of_day() == 3600 * 1000
