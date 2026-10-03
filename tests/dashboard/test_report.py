from pathlib import Path

from satrx.dashboard.report import render_html_report, write_report
from satrx.dashboard.scan import CaptureRecord


def _make_record(tmp_path: Path, with_image: bool, satellite_name: str = "METEOR-M2 3") -> CaptureRecord:
    image_path = None
    if with_image:
        image_path = tmp_path / "capture.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    return CaptureRecord(
        metadata_path=tmp_path / "capture.cs8.json",
        iq_file="capture.cs8",
        satellite_name=satellite_name,
        device="hackrf",
        center_freq_hz=137_900_000.0,
        sample_rate_hz=2_048_000.0,
        duration_s=660.0,
        gain_db=30.0,
        start_time_utc="2026-08-16T21:09:39+00:00",
        image_path=image_path,
    )


class TestRenderHtmlReport:

    def test_nominal_case_includes_metadata_fields(self, tmp_path: Path) -> None:
        record = _make_record(tmp_path, with_image=False)

        html = render_html_report([record])

        assert "METEOR-M2 3" in html
        assert "137.900 MHz" in html
        assert "hackrf" in html
        assert "<!doctype html>" in html.lower()

    def test_nominal_case_embeds_image_as_data_uri(self, tmp_path: Path) -> None:
        record = _make_record(tmp_path, with_image=True)

        html = render_html_report([record])

        assert "data:image/png;base64," in html

    def test_edge_case_empty_records_list(self) -> None:
        html = render_html_report([])

        assert "Aucune capture trouvee" in html
        assert "0 capture(s)" in html

    def test_edge_case_escapes_untrusted_satellite_name(self, tmp_path: Path) -> None:
        record = _make_record(tmp_path, with_image=False, satellite_name="<script>alert(1)</script>")

        html = render_html_report([record])

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_interop_write_report_creates_readable_file(self, tmp_path: Path) -> None:
        record = _make_record(tmp_path, with_image=True)
        output_path = tmp_path / "reports" / "dashboard.html"

        write_report([record], output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert content == render_html_report([record])
