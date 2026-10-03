import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from satrx.acquisition.params import SdrDevice
from satrx.tui.app import CapturePlan


def _sample_plan_dict() -> dict:
    return {
        "satellite_name": "METEOR-M2 3",
        "device": "hackrf_transfer",
        "center_freq_hz": 137.9e6,
        "sample_rate_hz": 2.048e6,
        "duration_s": 660.0,
        "lna_gain_db": 32.0,
        "gain_db": None,
        "amplifier_enabled": False,
        "start_at_utc": "2026-08-16T19:28:24+00:00",
        "output_dir": "data/raw",
        "trajectory": [
            {"seconds_from_start": 0.0, "elevation_deg": 10.0, "azimuth_deg": 133.0},
            {"seconds_from_start": 300.0, "elevation_deg": 39.6, "azimuth_deg": 65.0},
        ],
    }


class TestCapturePlanFromJsonFile:

    def test_nominal_case(self, tmp_path):
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(_sample_plan_dict()))

        plan = CapturePlan.from_json_file(path)

        assert plan.satellite_name == "METEOR-M2 3"
        assert plan.device is SdrDevice.HACKRF
        assert plan.center_freq_hz == pytest.approx(137.9e6)
        assert plan.start_at_utc == datetime(2026, 8, 16, 19, 28, 24, tzinfo=timezone.utc)
        assert plan.output_dir == Path("data/raw")
        assert len(plan.trajectory) == 2
        assert plan.trajectory[1].elevation_deg == pytest.approx(39.6)

    def test_edge_case_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CapturePlan.from_json_file(tmp_path / "does_not_exist.json")

    def test_interop_lna_gain_default_none(self, tmp_path):
        data = _sample_plan_dict()
        del data["lna_gain_db"]
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(data))

        plan = CapturePlan.from_json_file(path)

        assert plan.lna_gain_db is None
