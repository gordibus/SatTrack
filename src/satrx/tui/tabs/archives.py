from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Label

from satrx.dashboard.scan import CaptureRecord, scan_recordings
from satrx.tui.protocol import check_image_readability


def _size_str(path: Path) -> str:
    try:
        b = path.stat().st_size
    except OSError:
        return "-"
    if b >= 1_073_741_824:
        return f"{b/1_073_741_824:.1f} Go"
    if b >= 1_048_576:
        return f"{b/1_048_576:.1f} Mo"
    return f"{b/1024:.0f} Ko"


def _snr_str(gain: Optional[float]) -> str:
    # SNR non disponible dans le sidecar ; on affiche le gain enregistre
    return f"gain {gain:.0f}dB" if gain is not None else "-"


class ArchivesTab(Vertical):
    DEFAULT_CSS = """
    ArchivesTab {
        height: 1fr;
    }
    #archives-summary {
        height: 1;
        padding: 0 1;
        color: #4A6A82;
    }
    #archives-table {
        height: 1fr;
        border: round #182638;
    }
    #archives-actions {
        height: 3;
        padding: 0 1;
    }
    #btn-decode-sel {
        width: 14;
    }
    #btn-security-sel {
        width: 22;
        margin-left: 1;
    }
    #btn-dashboard {
        width: 26;
        margin-left: 1;
    }
    #btn-open-image {
        width: 18;
        margin-left: 1;
    }
    """

    _records: reactive[list[CaptureRecord]] = reactive([])

    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
        on_decode: Optional[object] = None,
        on_security: Optional[object] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._raw_dir = raw_dir
        self._processed_dir = processed_dir
        self._on_decode = on_decode
        self._on_security = on_security
        self._readability: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("", id="archives-summary")
        yield DataTable(id="archives-table", cursor_type="row")
        with Horizontal(id="archives-actions"):
            yield Button("Decoder", id="btn-decode-sel", variant="primary")
            yield Button("Analyser securite", id="btn-security-sel", variant="default")
            yield Button("Dashboard HTML", id="btn-dashboard", variant="default")
            yield Button("Ouvrir image", id="btn-open-image", variant="default")

    def on_mount(self) -> None:
        table = self.query_one("#archives-table", DataTable)
        table.add_columns(
            "Fichier IQ", "Taille", "Image", "Gain", "Lisible"
        )
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-decode-sel":
            rec = self._selected_record()
            if rec and callable(self._on_decode):
                self._on_decode(self._raw_dir / rec.iq_file)
        elif event.button.id == "btn-security-sel":
            rec = self._selected_record()
            if rec and callable(self._on_security):
                self._on_security(self._raw_dir / rec.iq_file)
        elif event.button.id == "btn-dashboard":
            self._generate_dashboard()
        elif event.button.id == "btn-open-image":
            rec = self._selected_record()
            if rec and rec.image_path is not None:
                try:
                    subprocess.Popen(["xdg-open", str(rec.image_path)])
                except OSError:
                    pass

    @work(thread=True)
    def _refresh(self) -> None:
        try:
            records = scan_recordings(self._raw_dir, self._processed_dir)
        except Exception:
            records = []
        self._records = records

        # Calcul de lisibilite pour les images
        readability: dict[str, str] = {}
        for rec in records:
            if rec.image_path is not None:
                result = check_image_readability(rec.image_path)
                readability[rec.iq_file] = result.status
            else:
                readability[rec.iq_file] = "-"

        self._readability = readability
        self.app.call_from_thread(self._render_table)

    def _render_table(self) -> None:
        table = self.query_one("#archives-table", DataTable)
        table.clear()

        total_raw = sum(
            (self._raw_dir / r.iq_file).stat().st_size
            for r in self._records
            if (self._raw_dir / r.iq_file).exists()
        )
        count_img = sum(1 for r in self._records if r.image_path is not None)
        raw_str = f"{total_raw/1e9:.1f} Go" if total_raw >= 1e9 else f"{total_raw/1e6:.0f} Mo"
        self.query_one("#archives-summary", Label).update(
            f"data/raw : {raw_str} ({len(self._records)} fichiers)   "
            f"data/processed : {count_img} image(s)"
        )

        for rec in self._records:
            iq_path = self._raw_dir / rec.iq_file
            size = _size_str(iq_path)
            has_img = "[bold #4DC88A]✓ PNG[/]" if rec.image_path else "[dim]✗ -[/]"
            gain = _snr_str(rec.gain_db)
            readable = self._readability.get(rec.iq_file, "-")
            if readable == "OK" or readable == "OK (header)":
                readable_cell = "[bold #4DC88A]✓[/]"
            elif readable == "chiffre ?":
                readable_cell = "[bold #E05050]✗ chiffre ?[/]"
            elif readable == "corrompu":
                readable_cell = "[bold #E2934A]✗ corrompu[/]"
            else:
                readable_cell = "[dim]-[/]"
            name = rec.iq_file[:45] + "…" if len(rec.iq_file) > 46 else rec.iq_file
            table.add_row(name, size, has_img, gain, readable_cell)

    def _selected_record(self) -> Optional[CaptureRecord]:
        table = self.query_one("#archives-table", DataTable)
        idx = table.cursor_row
        if 0 <= idx < len(self._records):
            return self._records[idx]
        return None

    @work(thread=True)
    def _generate_dashboard(self) -> None:
        try:
            import subprocess as sp
            sp.run(
                ["poetry", "run", "python", "scripts/generate_dashboard.py"],
                cwd=Path(__file__).resolve().parent.parent.parent.parent.parent,
                timeout=30,
            )
            self.app.call_from_thread(
                lambda: self.app.notify("Dashboard HTML genere dans data/processed/dashboard.html")
            )
        except Exception as e:
            err_msg = str(e)
            self.app.call_from_thread(
                lambda m=err_msg: self.app.notify(f"Erreur dashboard : {m}", severity="error")
            )
