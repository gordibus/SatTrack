import json
from datetime import datetime, timezone

import pytest

from satrx.acquisition.params import RecordingParams, SdrDevice
from satrx.acquisition.recorder import RecordingMetadata, parse_hackrf_stats_line, write_metadata_sidecar

# record_iq()/start_recording_process() lancent un vrai binaire (rtl_sdr/hackrf_transfer) via
# subprocess : non testes ici, a couvrir par un test d'integration necessitant le materiel SDR
# (tests/integration/). parse_hackrf_stats_line() est la logique pure isolee de cette I/O.

PARAMS = RecordingParams(
    satellite_name="METEOR-M2 3",
    center_freq_hz=137.1e6,
    sample_rate_hz=1.024e6,
    duration_s=600.0,
    gain_db=40.0,
)


class TestRecordingMetadataToDict:

    def test_nominal_case(self):
        metadata = RecordingMetadata(
            params=PARAMS,
            device=SdrDevice.RTL_SDR,
            start_time_utc=datetime(2026, 8, 16, 19, 30, 0, tzinfo=timezone.utc),
            output_file="20260816T193000Z_METEOR-M2-3_137.100MHz.iq",
        )

        data = metadata.to_dict()

        assert data["satellite_name"] == "METEOR-M2 3"
        assert data["device"] == "rtl_sdr"
        assert data["center_freq_hz"] == PARAMS.center_freq_hz
        assert data["start_time_utc"] == "2026-08-16T19:30:00+00:00"

    def test_edge_case_no_gain_is_json_serializable(self):
        params_no_gain = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.1e6,
            sample_rate_hz=1.024e6,
            duration_s=600.0,
        )
        metadata = RecordingMetadata(
            params=params_no_gain,
            device=SdrDevice.HACKRF,
            start_time_utc=datetime(2026, 8, 16, 19, 30, 0, tzinfo=timezone.utc),
            output_file="out.cs8",
        )

        serialized = json.dumps(metadata.to_dict())

        assert json.loads(serialized)["gain_db"] is None


class TestWriteMetadataSidecar:

    def test_interop_roundtrip_through_json_file(self, tmp_path):
        metadata = RecordingMetadata(
            params=PARAMS,
            device=SdrDevice.RTL_SDR,
            start_time_utc=datetime(2026, 8, 16, 19, 30, 0, tzinfo=timezone.utc),
            output_file="20260816T193000Z_METEOR-M2-3_137.100MHz.iq",
        )
        sidecar_path = tmp_path / "recording.iq.json"

        write_metadata_sidecar(metadata, sidecar_path)

        loaded = json.loads(sidecar_path.read_text())
        assert loaded == metadata.to_dict()


class TestParseHackrfStatsLine:

    def test_nominal_case_real_captured_line(self):
        # ligne reellement capturee lors du test materiel du 16/08/2026 (HackRF One, sans antenne)
        line = " 4.2 MiB / 1.000 sec =  4.2 MiB/second, average power -42.1 dBfs"

        stats = parse_hackrf_stats_line(line)

        assert stats is not None
        assert stats.mib_transferred == pytest.approx(4.2)
        assert stats.mib_per_second == pytest.approx(4.2)
        assert stats.average_power_dbfs == pytest.approx(-42.1)

    def test_nominal_case_negative_and_positive_power(self):
        stats = parse_hackrf_stats_line(" 1.0 MiB / 1.000 sec =  1.0 MiB/second, average power 3.5 dBfs")

        assert stats is not None
        assert stats.average_power_dbfs == pytest.approx(3.5)

    def test_edge_case_non_matching_line_returns_none(self):
        assert parse_hackrf_stats_line("call hackrf_set_sample_rate(2048000 Hz)") is None
        assert parse_hackrf_stats_line("") is None
