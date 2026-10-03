from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Label, Log, Select, Static

from satrx.tui.protocol import detect_protocol


class DecodeTab(Vertical):
    DEFAULT_CSS = """
    DecodeTab {
        height: 1fr;
    }
    #file-row {
        height: 3;
        padding: 0 1;
    }
    #file-select {
        width: 1fr;
    }
    #btn-decode-start {
        width: 14;
        margin-left: 1;
    }
    #proto-panel {
        height: auto;
        border: round #182638;
        padding: 1 2;
        background: #0D1520;
        margin: 0 1;
    }
    #pipeline-table {
        height: 10;
        border: round #182638;
        margin: 0 1;
    }
    #decode-counters {
        height: 3;
        padding: 0 2;
        color: #4A6A82;
    }
    #decode-log {
        height: 1fr;
        border: round #1a6b66;
        background: #05050a;
        color: #0dd3c4;
        margin: 0 1;
    }
    """

    _selected_file: reactive[Optional[Path]] = reactive(None)
    _decoding: reactive[bool] = reactive(False)
    _frames_ok: reactive[int] = reactive(0)
    _frames_err: reactive[int] = reactive(0)
    _rs_corrected: reactive[int] = reactive(0)

    # Etapes du pipeline : (id, label)
    _PIPELINE_STEPS = [
        ("costas",       "Costas loop (recouvrement porteuse)"),
        ("timing",       "Timing recovery (recouvrement symbole)"),
        ("derand",       "Derandomisation CCSDS"),
        ("viterbi",      "Viterbi K=7 (numpy vectorise)"),
        ("rs",           "Reed-Solomon RS(255,223) batch"),
        ("framesync",    "Synchro trame ASM / CADU"),
        ("jpeg",         "JPEG/DCT -> MCU -> image"),
    ]

    def __init__(self, raw_dir: Path, processed_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._raw_dir = raw_dir
        self._processed_dir = processed_dir
        self._step_status: dict[str, str] = {sid: " " for sid, _ in self._PIPELINE_STEPS}
        self._step_time: dict[str, str] = {sid: "-" for sid, _ in self._PIPELINE_STEPS}

    def compose(self) -> ComposeResult:
        with Horizontal(id="file-row"):
            yield Select([], id="file-select", prompt="Choisir un fichier IQ...")
            yield Button("Demarrer", id="btn-decode-start", variant="primary")
        yield Static("", id="proto-panel")
        yield DataTable(id="pipeline-table", cursor_type="none")
        yield Label("", id="decode-counters")
        yield Log(id="decode-log", highlight=False)

    def on_mount(self) -> None:
        table = self.query_one("#pipeline-table", DataTable)
        table.add_columns("Etat", "Etape", "Duree")
        for sid, label in self._PIPELINE_STEPS:
            table.add_row("[ ]", label, "-", key=sid)
        self._populate_file_list()

    def _populate_file_list(self) -> None:
        files = sorted(self._raw_dir.glob("*.cs8"))
        sel = self.query_one("#file-select", Select)
        options = [(f.name, str(f)) for f in files]
        if options:
            sel.set_options(options)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value and event.value != Select.BLANK:
            p = Path(str(event.value))
            self._selected_file = p
            self._refresh_proto_panel(p)

    def _refresh_proto_panel(self, path: Path) -> None:
        sidecar = path.with_suffix(path.suffix + ".json")
        proto = detect_protocol(sidecar)
        panel = self.query_one("#proto-panel", Static)
        if proto is None:
            panel.update(
                f"[dim]Frequence centre non identifiee - verifier le sidecar .json[/]\n"
                f"Fichier : {path.name}"
            )
            return
        lines = [
            f"[bold #1EB8A0]Protocole detecte[/] : [bold]{proto.name}[/]",
            f"  Modulation    : {proto.modulation}",
            f"  FEC           : {proto.fec}",
            f"  Synchro trame : {proto.frame_sync}",
            f"  Freq centre   : {proto.center_freq_mhz:.3f} MHz",
        ]
        panel.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-decode-start" and not self._decoding:
            f = self._selected_file
            if f is not None:
                self._start_decode(f)

    def _set_step(self, step_id: str, status: str, duration: str) -> None:
        self._step_status[step_id] = status
        self._step_time[step_id] = duration
        table = self.query_one("#pipeline-table", DataTable)
        table.update_cell(step_id, "Etat", status)
        table.update_cell(step_id, "Duree", duration)

    def _update_counters(self) -> None:
        self.query_one("#decode-counters", Label).update(
            f"[bold]Trames OK[/] {self._frames_ok}   "
            f"[bold]Erreurs RS corrigees[/] {self._rs_corrected}   "
            f"[bold]Rejetes[/] {self._frames_err}"
        )

    @work(thread=True)
    def _start_decode(self, iq_path: Path) -> None:
        self._decoding = True
        log = self.query_one(Log)
        self.app.call_from_thread(log.clear)
        self.app.call_from_thread(log.write_line, f"Debut decodage : {iq_path.name}")

        # Reset pipeline display
        for sid, _ in self._PIPELINE_STEPS:
            self.app.call_from_thread(self._set_step, sid, "[ ]", "-")
        self._frames_ok = 0
        self._frames_err = 0
        self._rs_corrected = 0

        sidecar = iq_path.with_suffix(iq_path.suffix + ".json")
        proto = detect_protocol(sidecar)

        if proto is None or proto.name not in ("LRPT", "APT"):
            self.app.call_from_thread(
                log.write_line,
                "⚠ Protocole non supporte ou non detecte - seuls LRPT et APT sont pris en charge.",
            )
            self._decoding = False
            return

        if proto.name == "APT":
            self._decode_apt(iq_path, log)
        else:
            self._decode_lrpt(iq_path, log)

        self._decoding = False

    def _decode_lrpt(self, iq_path: Path, log: Log) -> None:
        import numpy as np
        from satrx.demod.costas import costas_loop_qpsk
        from satrx.demod.timing_recovery import estimate_symbol_timing_offset
        from satrx.decode.derandomize import derandomize
        from satrx.decode.frame_sync import extract_frames
        from satrx.decode.viterbi import viterbi_decode
        from satrx.decode.reed_solomon import rs_decode_batch

        CHUNK = 2_000_000   # octets IQ a charger d'un coup (2 Mo par chunk)
        SPS = 2_048_000 // 72_000  # ~28 samples/symbole

        t0 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "costas", "[·]", "en cours...")

        try:
            with open(iq_path, "rb") as f:
                raw = f.read(CHUNK)
            iq = np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 127.5
            iq_c = iq[0::2] + 1j * iq[1::2]

            result = costas_loop_qpsk(iq_c)
            symbols = result.corrected_symbols
            t1 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "costas", "[✓]", f"{t1-t0:.2f} s")
            self.app.call_from_thread(log.write_line, f"✓ Costas loop : {len(symbols)} symboles")
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "costas", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ Costas : {exc}")
            return

        t2 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "timing", "[·]", "en cours...")
        try:
            offset_frac = estimate_symbol_timing_offset(symbols, SPS)
            offset = int(round(offset_frac))
            bits_raw = np.real(symbols[offset::SPS])
            bits = (bits_raw > 0).astype(np.int8).tolist()
            t3 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "timing", "[✓]", f"{t3-t2:.2f} s")
            self.app.call_from_thread(log.write_line, f"✓ Timing : {len(bits)} bits")
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "timing", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ Timing : {exc}")
            return

        t4 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "derand", "[·]", "en cours...")
        try:
            raw_bytes = bytes(
                int("".join(str(b) for b in bits[i:i+8]), 2)
                for i in range(0, len(bits) - len(bits) % 8, 8)
            )
            derand = derandomize(raw_bytes)
            t5 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "derand", "[✓]", f"{t5-t4:.2f} s")
            self.app.call_from_thread(log.write_line, f"✓ Derandomisation : {len(derand)} octets")
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "derand", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ Derandomisation : {exc}")
            return

        t6 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "viterbi", "[·]", "en cours...")
        try:
            decoded_bits = viterbi_decode(list(bits))
            t7 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "viterbi", "[✓]", f"{t7-t6:.2f} s")
            self.app.call_from_thread(log.write_line, f"✓ Viterbi : {len(decoded_bits)} bits")
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "viterbi", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ Viterbi : {exc}")
            return

        t8 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "rs", "[·]", "en cours...")
        try:
            decoded_bytes = bytes(
                int("".join(str(b) for b in decoded_bits[i:i+8]), 2)
                for i in range(0, len(decoded_bits) - len(decoded_bits) % 8, 8)
            )
            codewords = [list(decoded_bytes[i:i+255]) for i in range(0, len(decoded_bytes)-254, 255)]
            corrected = rs_decode_batch(codewords)
            self._rs_corrected = sum(
                1 for a, b in zip(codewords, corrected) if a != b
            )
            t9 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "rs", "[✓]", f"{t9-t8:.2f} s")
            self.app.call_from_thread(
                log.write_line,
                f"✓ RS batch : {len(corrected)} mots, {self._rs_corrected} corriges",
            )
            self.app.call_from_thread(self._update_counters)
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "rs", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ RS : {exc}")
            return

        t10 = time.perf_counter()
        self.app.call_from_thread(self._set_step, "framesync", "[·]", "en cours...")
        try:
            data_bytes = bytes(b for cw in corrected for b in cw[:223])
            frames = extract_frames(list(data_bytes), frame_length_bits=1024 * 8)
            self._frames_ok = len(frames)
            t11 = time.perf_counter()
            self.app.call_from_thread(self._set_step, "framesync", "[✓]", f"{t11-t10:.2f} s")
            self.app.call_from_thread(log.write_line, f"✓ Synchro trame : {len(frames)} CADU")
            self.app.call_from_thread(self._update_counters)
        except Exception as exc:
            self.app.call_from_thread(self._set_step, "framesync", "[✗]", "erreur")
            self.app.call_from_thread(log.write_line, f"✖ Framesync : {exc}")
            return

        if not frames:
            self.app.call_from_thread(
                log.write_line,
                "⚠ Aucune trame synchronisee - signal insuffisant ou capture incomplete.",
            )
            self.app.call_from_thread(self._set_step, "jpeg", "[ ]", "- (pas de trame)")
            return

        self.app.call_from_thread(self._set_step, "jpeg", "[·]", "en cours...")
        self.app.call_from_thread(log.write_line, "JPEG/DCT : reconstruction image en cours...")
        self.app.call_from_thread(self._set_step, "jpeg", "[~]", "voir log")
        self.app.call_from_thread(
            log.write_line,
            "ℹ  Reconstruction JPEG complete necessitant un passage complet - "
            "voir scripts/decode_lrpt.py pour le pipeline entier.",
        )

    def _decode_apt(self, iq_path: Path, log: Log) -> None:
        self.app.call_from_thread(log.write_line, "Pipeline APT (analogique FM) - non implemente dans ce TUI.")
        self.app.call_from_thread(
            log.write_line,
            "Utiliser : poetry run python scripts/decode_apt.py --input " + str(iq_path),
        )

    def preselect_file(self, path: Path) -> None:
        """Preselectionne un fichier IQ (appele depuis l'onglet Archives ou Active)."""
        self._selected_file = path
        sel = self.query_one("#file-select", Select)
        sel.value = str(path)
        self._refresh_proto_panel(path)
