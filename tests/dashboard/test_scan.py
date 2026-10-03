import json
from pathlib import Path

import pytest

from satrx.dashboard.scan import scan_recordings

_SAMPLE_METADATA = {
    "satellite_name": "METEOR-M2 3",
    "device": "hackrf",
    "center_freq_hz": 137_900_000.0,
    "sample_rate_hz": 2_048_000.0,
    "duration_s": 660.0,
    "gain_db": 30.0,
    "start_time_utc": "2026-08-16T21:09:39+00:00",
    "output_file": "20260816T210939Z_METEOR-M2-3_137.900MHz.cs8",
}


def _write_sidecar(raw_dir: Path, data: dict[str, object]) -> Path:
    path = raw_dir / f"{data['output_file']}.json"
    path.write_text(json.dumps(data))
    return path


class TestScanRecordings:

    def test_nominal_case_finds_metadata_and_matching_image(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()
        _write_sidecar(raw_dir, _SAMPLE_METADATA)
        image_path = processed_dir / "20260816T210939Z_METEOR-M2-3_137.900MHz.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        records = scan_recordings(raw_dir, processed_dir)

        assert len(records) == 1
        record = records[0]
        assert record.satellite_name == "METEOR-M2 3"
        assert record.center_freq_hz == 137_900_000.0
        assert record.gain_db == 30.0
        assert record.image_path == image_path

    def test_nominal_case_no_processed_dir_gives_no_image(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_sidecar(raw_dir, _SAMPLE_METADATA)

        records = scan_recordings(raw_dir)

        assert len(records) == 1
        assert records[0].image_path is None

    def test_edge_case_raw_dir_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            scan_recordings(tmp_path / "does-not-exist")

    def test_edge_case_empty_raw_dir(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        records = scan_recordings(raw_dir)

        assert records == []

    def test_edge_case_missing_gain_db_defaults_to_none(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        data = dict(_SAMPLE_METADATA)
        data["gain_db"] = None
        _write_sidecar(raw_dir, data)

        records = scan_recordings(raw_dir)

        assert records[0].gain_db is None

    def test_interop_output_directly_consumable_by_render_html_report(self, tmp_path: Path) -> None:
        from satrx.dashboard.report import render_html_report

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_sidecar(raw_dir, _SAMPLE_METADATA)

        records = scan_recordings(raw_dir)
        html = render_html_report(records)

        assert "METEOR-M2 3" in html
