from __future__ import annotations

import base64
from html import escape
from pathlib import Path

from satrx.dashboard.scan import CaptureRecord

_PAGE_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>SatRX - Tableau de bord des captures</title>
<style>
body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
h1 {{ color: #58a6ff; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #30363d; padding: 0.5rem; text-align: left; vertical-align: top; }}
th {{ background: #161b22; }}
.capture-image {{ max-width: 200px; max-height: 200px; }}
.no-image {{ color: #8b949e; font-style: italic; }}
</style>
</head>
<body>
<h1>SatRX - Tableau de bord des captures</h1>
<p>{n_records} capture(s) recensee(s).</p>
<table>
<thead>
<tr>
<th>Satellite</th><th>Debut (UTC)</th><th>Frequence</th><th>Taux d'echantillonnage</th>
<th>Duree</th><th>Gain (dB)</th><th>Peripherique</th><th>Image</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>
</body>
</html>
"""


def _image_data_uri(image_path: Path) -> str:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_row(record: CaptureRecord) -> str:
    if record.image_path is not None:
        image_html = (
            f'<img class="capture-image" alt="{escape(record.satellite_name)}" '
            f'src="{_image_data_uri(record.image_path)}">'
        )
    else:
        image_html = '<span class="no-image">aucune image</span>'

    gain_text = f"{record.gain_db:.0f}" if record.gain_db is not None else "-"

    return (
        "<tr>"
        f"<td>{escape(record.satellite_name)}</td>"
        f"<td>{escape(record.start_time_utc)}</td>"
        f"<td>{record.center_freq_hz / 1e6:.3f} MHz</td>"
        f"<td>{record.sample_rate_hz / 1e6:.3f} Msps</td>"
        f"<td>{record.duration_s:.0f} s</td>"
        f"<td>{gain_text}</td>"
        f"<td>{escape(record.device)}</td>"
        f"<td>{image_html}</td>"
        "</tr>"
    )


def render_html_report(records: list[CaptureRecord]) -> str:
    rows = [_render_row(record) for record in records]
    table_rows = "\n".join(rows) if rows else '<tr><td colspan="8">Aucune capture trouvee.</td></tr>'
    return _PAGE_TEMPLATE.format(n_records=len(records), table_rows=table_rows)


def write_report(records: list[CaptureRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html_report(records))
