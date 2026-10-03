from datetime import datetime, timezone

import pytest

from satrx.telemetry.cuc_time import decode_cuc_time


class TestDecodeCucTime:

    def test_nominal_case(self):
        data = (100).to_bytes(4, "big") + (0x8000).to_bytes(2, "big")

        cuc = decode_cuc_time(data)

        assert cuc.coarse_seconds == 100
        assert cuc.fine_fraction == pytest.approx(0.5)

    def test_nominal_case_no_fine_time(self):
        data = (12345).to_bytes(4, "big")

        cuc = decode_cuc_time(data, coarse_bytes=4, fine_bytes=0)

        assert cuc.coarse_seconds == 12345
        assert cuc.fine_fraction == 0.0

    def test_edge_case_data_too_short(self):
        with pytest.raises(ValueError):
            decode_cuc_time(b"\x00\x01\x02")

    def test_edge_case_invalid_coarse_bytes(self):
        with pytest.raises(ValueError):
            decode_cuc_time(b"\x00" * 6, coarse_bytes=0)

    def test_interop_to_datetime(self):
        data = (100).to_bytes(4, "big") + (0x8000).to_bytes(2, "big")
        cuc = decode_cuc_time(data)
        epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)

        result = cuc.to_datetime(epoch)

        assert result == datetime(2000, 1, 1, 0, 1, 40, 500000, tzinfo=timezone.utc)
