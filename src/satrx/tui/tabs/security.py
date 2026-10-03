from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Select, Static

from satrx.tui.protocol import classify_encoding, detect_protocol


_B8_FINDINGS = [
    ("☠", "FIND-01", "Cryptanalyse A5/GMR-1",     "CRITIQUE",  "#E05050"),
    ("⚠", "FIND-02", "Clonage IMSI",               "HAUTE",     "#E2934A"),
    ("⚠", "FIND-03", "Replay session",             "HAUTE",     "#E2934A"),
    ("⚠", "FIND-05", "Absence MAC",                "HAUTE",     "#E2934A"),
    ("ℹ", "FIND-04", "Billing gap",                "MOYENNE",   "#4A6A82"),
    ("ℹ", "FIND-06", "Taps A5/GMR-1 documentes",  "INFO",      "#4A6A82"),
]


def _bar(entropy: float, width: int = 24) -> str:
    filled = int((entropy / 8.0) * width)
    filled = max(0, min(width, filled))
    empty = width - filled
    return "█" * filled + "░" * empty


class SecurityTab(Vertical):
    DEFAULT_CSS = """
    SecurityTab {
        height: 1fr;
    }
    #sec-file-row {
        height: 3;
        padding: 0 1;
    }
    #sec-file-select {
        width: 1fr;
    }
    #btn-analyze {
        width: 14;
        margin-left: 1;
    }
    #auto-detect-panel {
        height: auto;
        border: round #182638;
        padding: 1 2;
        background: #0D1520;
        margin: 0 1;
    }
    #entropy-table {
        height: 8;
        border: round #182638;
        margin: 0 1;
    }
    #b8-panel {
        height: auto;
        border: round #182638;
        padding: 1 2;
        background: #0D1520;
        margin: 0 1;
    }
    """

    def __init__(self, raw_dir: Path, processed_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._raw_dir = raw_dir
        self._processed_dir = processed_dir

    def compose(self) -> ComposeResult:
        with Horizontal(id="sec-file-row"):
            yield Select([], id="sec-file-select", prompt="Choisir un fichier IQ ou image...")
            yield Button("Analyser", id="btn-analyze", variant="primary")
        yield Static("", id="auto-detect-panel")
        yield DataTable(id="entropy-table", cursor_type="none")
        yield Static("", id="b8-panel")

    def on_mount(self) -> None:
        table = self.query_one("#entropy-table", DataTable)
        table.add_columns("Source", "Entropie (bit/B)", "Barre", "Classification")
        self._populate_files()
        self._render_b8_panel()

    def _populate_files(self) -> None:
        files_iq = sorted(self._raw_dir.glob("*.cs8"))
        files_img = sorted(self._processed_dir.glob("*.png")) if self._processed_dir.exists() else []
        options = [(f.name, str(f)) for f in files_iq + files_img]
        sel = self.query_one("#sec-file-select", Select)
        if options:
            sel.set_options(options)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-analyze":
            sel = self.query_one("#sec-file-select", Select)
            if sel.value and sel.value != Select.BLANK:
                self._analyze(Path(str(sel.value)))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sec-file-select" and event.value and event.value != Select.BLANK:
            p = Path(str(event.value))
            sidecar = p.with_suffix(p.suffix + ".json")
            proto = detect_protocol(sidecar)
            panel = self.query_one("#auto-detect-panel", Static)
            if proto is not None:
                enc = "absent" if proto.name in ("LRPT", "APT", "HRPT") else "possible"
                lines = [
                    f"[bold #1EB8A0]Protocole[/] : {proto.name}",
                    f"  Modulation         : {proto.modulation}",
                    f"  FEC identifie      : {proto.fec}",
                    f"  Chiffrement contenu : {enc} (diffusion en clair pour {proto.name})",
                ]
                panel.update("\n".join(lines))
            else:
                panel.update("[dim]Sidecar absent - protocole non detecte automatiquement.[/]")

    @work(thread=True)
    def _analyze(self, path: Path) -> None:
        try:
            with path.open("rb") as f:
                data = f.read(1_000_000)
        except OSError as e:
            err_msg = str(e)
            self.app.call_from_thread(
                lambda m=err_msg: self.query_one("#auto-detect-panel", Static).update(f"✖ Erreur : {m}")
            )
            return

        # Entropie globale
        global_entropy = _shannon(data)

        # Analyse par blocs de 64 ko pour simuler des "APID" sans necessiter de decodage complet
        chunks = [data[i:i+65536] for i in range(0, len(data), 65536) if data[i:i+65536]]
        table = self.query_one("#entropy-table", DataTable)
        self.app.call_from_thread(table.clear)

        label, style = classify_encoding(global_entropy)
        self.app.call_from_thread(
            table.add_row,
            f"{path.name[:30]}",
            f"{global_entropy:.2f}",
            _bar(global_entropy),
            f"[{style}]{label}[/]",
        )

        for i, chunk in enumerate(chunks[:6], 1):
            blk_ent = _shannon(chunk)
            lbl, st = classify_encoding(blk_ent)
            self.app.call_from_thread(
                table.add_row,
                f"  bloc {i}",
                f"{blk_ent:.2f}",
                _bar(blk_ent),
                f"[{st}]{lbl}[/]",
            )

        sidecar = path.with_suffix(path.suffix + ".json")
        proto = detect_protocol(sidecar)
        extra = ""
        if proto:
            extra = (
                f"\n  Protocole detecte : {proto.name} - "
                f"chiffrement de contenu : absent (diffusion en clair)"
            )
            if proto.name in ("GMR-1 / GMR-2 (Inmarsat/Thuraya)",):
                extra = (
                    f"\n  Protocole detecte : {proto.name}\n"
                    f"  Algorithme A5/GMR-1 : faible (cf. FIND-01 rapport B8)"
                )

        panel_lines = [
            f"[bold #1EB8A0]Analyse complete[/] : {path.name}",
            f"  Entropie globale   : {global_entropy:.2f} bit/B",
        ]
        lbl, st = classify_encoding(global_entropy)
        panel_lines.append(f"  Classification     : [{st}]{lbl}[/]")
        if extra:
            panel_lines.append(extra)

        self.app.call_from_thread(
            lambda: self.query_one("#auto-detect-panel", Static).update("\n".join(panel_lines))
        )

    def _render_b8_panel(self) -> None:
        lines = ["[bold #1EB8A0]Rapport audit B8[/]  docs/audit_b8_lab_report.md", ""]
        for sym, fid, title, severity, color in _B8_FINDINGS:
            lines.append(f"  [{color}]{sym} {fid}[/]  {title:<40}  [{color}]{severity}[/]")
        self.query_one("#b8-panel", Static).update("\n".join(lines))


def _shannon(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
