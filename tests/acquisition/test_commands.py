from datetime import datetime, timezone
from pathlib import Path

import pytest

from satrx.acquisition.commands import (
    build_hackrf_transfer_command,
    build_recording_filename,
    build_rtl_sdr_command,
)
from satrx.acquisition.params import RecordingParams

PARAMS = RecordingParams(
    satellite_name="METEOR-M2 3",
    center_freq_hz=137.1e6,
    sample_rate_hz=1.024e6,
    duration_s=10.0,
    gain_db=40.0,
)


class TestBuildRecordingFilename:

    def test_nominal_case(self):
        start = datetime(2026, 8, 16, 19, 30, 0, tzinfo=timezone.utc)

        filename = build_recording_filename(PARAMS, start, extension="iq")

        assert filename == "20260816T193000Z_METEOR-M2-3_137.100MHz.iq"

    def test_edge_case_naive_datetime(self):
        start = datetime(2026, 8, 16, 19, 30, 0)

        with pytest.raises(ValueError):
            build_recording_filename(PARAMS, start, extension="iq")


class TestBuildRtlSdrCommand:

    def test_nominal_case(self):
        command = build_rtl_sdr_command(PARAMS, Path("/tmp/out.iq"))

        assert command[0] == "rtl_sdr"
        assert "-f" in command and command[command.index("-f") + 1] == "137100000"
        assert "-s" in command and command[command.index("-s") + 1] == "1024000"
        assert "-g" in command and command[command.index("-g") + 1] == "40.0"
        assert command[-1] == "/tmp/out.iq"

    def test_nominal_case_sample_count_matches_duration(self):
        command = build_rtl_sdr_command(PARAMS, Path("/tmp/out.iq"))

        n_samples = int(command[command.index("-n") + 1])
        assert n_samples == int(PARAMS.duration_s * PARAMS.sample_rate_hz)

    def test_edge_case_no_gain_omits_flag(self):
        params_no_gain = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.1e6,
            sample_rate_hz=1.024e6,
            duration_s=10.0,
        )

        command = build_rtl_sdr_command(params_no_gain, Path("/tmp/out.iq"))

        assert "-g" not in command


class TestBuildHackrfTransferCommand:

    def test_nominal_case(self):
        command = build_hackrf_transfer_command(PARAMS, Path("/tmp/out.cs8"))

        assert command[0] == "hackrf_transfer"
        assert "-r" in command and command[command.index("-r") + 1] == "/tmp/out.cs8"
        assert "-f" in command and command[command.index("-f") + 1] == "137100000"

    def test_interop_with_build_recording_filename(self, tmp_path):
        start = datetime(2026, 8, 16, 19, 30, 0, tzinfo=timezone.utc)
        filename = build_recording_filename(PARAMS, start, extension="cs8")
        output_path = tmp_path / filename

        command = build_hackrf_transfer_command(PARAMS, output_path)

        assert command[command.index("-r") + 1] == str(output_path)

    def test_nominal_case_lna_gain_and_amplifier(self):
        params = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.9e6,
            sample_rate_hz=2.048e6,
            duration_s=660.0,
            lna_gain_db=32.0,
            amplifier_enabled=True,
        )

        command = build_hackrf_transfer_command(params, Path("/tmp/out.cs8"))

        assert command[command.index("-l") + 1] == "32"
        assert command[command.index("-a") + 1] == "1"

    def test_edge_case_no_lna_gain_or_amplifier_omits_flags(self):
        params = RecordingParams(
            satellite_name="METEOR-M2 3",
            center_freq_hz=137.9e6,
            sample_rate_hz=2.048e6,
            duration_s=660.0,
        )

        command = build_hackrf_transfer_command(params, Path("/tmp/out.cs8"))

        assert "-l" not in command
        assert "-a" not in command
