from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static, Switch

from satrx.tui.hardware import detect_hardware
from satrx.tui.models import AppConfig, save_config


class ConfigTab(Vertical):
    DEFAULT_CSS = """
    ConfigTab {
        height: 1fr;
        padding: 1 2;
    }
    .section-title {
        color: #1EB8A0;
        text-style: bold;
        padding-top: 1;
    }
    .field-row {
        height: 3;
        margin-bottom: 0;
    }
    .field-label {
        width: 28;
        content-align: left middle;
        color: #C8DFF0;
    }
    .field-input {
        width: 30;
    }
    #hw-status-panel {
        height: auto;
        border: round #182638;
        padding: 1 2;
        background: #0D1520;
        margin-top: 1;
    }
    #config-actions {
        height: 3;
        margin-top: 1;
    }
    #btn-save-cfg {
        width: 16;
    }
    #btn-detect-hw {
        width: 26;
        margin-left: 1;
    }
    #btn-reset-cfg {
        width: 18;
        margin-left: 1;
    }
    """

    def __init__(
        self,
        config: AppConfig,
        config_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._config_path = config_path

    def compose(self) -> ComposeResult:
        yield Label("Station sol", classes="section-title")

        with Horizontal(classes="field-row"):
            yield Label("Nom de station", classes="field-label")
            yield Input(self._config.station_name, id="cfg-station-name", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Latitude (deg)", classes="field-label")
            yield Input(str(self._config.latitude_deg), id="cfg-lat", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Longitude (deg)", classes="field-label")
            yield Input(str(self._config.longitude_deg), id="cfg-lon", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Altitude (m)", classes="field-label")
            yield Input(str(self._config.elevation_m), id="cfg-elev", classes="field-input")

        yield Label("SDR et gains par defaut", classes="section-title")

        with Horizontal(classes="field-row"):
            yield Label("LNA gain (dB)", classes="field-label")
            yield Input(str(self._config.default_lna_gain_db), id="cfg-lna", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("VGA gain (dB)", classes="field-label")
            yield Input(str(self._config.default_vga_gain_db), id="cfg-vga", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Amplificateur", classes="field-label")
            yield Switch(value=self._config.default_amplifier, id="cfg-amp")
        with Horizontal(classes="field-row"):
            yield Label("Sample rate (Msps)", classes="field-label")
            yield Input(
                str(self._config.default_sample_rate_msps), id="cfg-srate", classes="field-input"
            )
        with Horizontal(classes="field-row"):
            yield Label("Correction PPM HackRF", classes="field-label")
            yield Input(str(self._config.ppm_correction), id="cfg-ppm", classes="field-input")

        yield Label("Répertoires et options", classes="section-title")

        with Horizontal(classes="field-row"):
            yield Label("Dossier bruts (raw)", classes="field-label")
            yield Input(self._config.raw_dir, id="cfg-raw-dir", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Dossier traites", classes="field-label")
            yield Input(self._config.processed_dir, id="cfg-proc-dir", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("Refresh TLE (heures)", classes="field-label")
            yield Input(str(self._config.tle_refresh_hours), id="cfg-tle-h", classes="field-input")

        yield Static("", id="hw-status-panel")

        with Horizontal(id="config-actions"):
            yield Button("Sauvegarder", id="btn-save-cfg", variant="success")
            yield Button("⚙ Detecter le materiel", id="btn-detect-hw", variant="default")
            yield Button("Reinitialiser", id="btn-reset-cfg", variant="warning")

    def on_mount(self) -> None:
        self._detect_hardware()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-cfg":
            self._save()
        elif event.button.id == "btn-detect-hw":
            self._detect_hardware()
        elif event.button.id == "btn-reset-cfg":
            self._reset()

    def _save(self) -> None:
        def _v(wid: str) -> str:
            return self.query_one(f"#{wid}", Input).value.strip()

        try:
            self._config.station_name = _v("cfg-station-name")
            self._config.latitude_deg = float(_v("cfg-lat"))
            self._config.longitude_deg = float(_v("cfg-lon"))
            self._config.elevation_m = float(_v("cfg-elev"))
            self._config.default_lna_gain_db = float(_v("cfg-lna"))
            self._config.default_vga_gain_db = float(_v("cfg-vga"))
            self._config.default_amplifier = self.query_one("#cfg-amp", Switch).value
            self._config.default_sample_rate_msps = float(_v("cfg-srate"))
            self._config.ppm_correction = int(_v("cfg-ppm"))
            self._config.raw_dir = _v("cfg-raw-dir")
            self._config.processed_dir = _v("cfg-proc-dir")
            self._config.tle_refresh_hours = int(_v("cfg-tle-h"))

            if self._config_path is not None:
                save_config(self._config_path, self._config)
            self.app.notify("Configuration sauvegardee.")
        except ValueError as exc:
            self.app.notify(f"Erreur de valeur : {exc}", severity="error")

    def _reset(self) -> None:
        default = AppConfig()
        self._config = default
        self.query_one("#cfg-station-name", Input).value = default.station_name
        self.query_one("#cfg-lat", Input).value = str(default.latitude_deg)
        self.query_one("#cfg-lon", Input).value = str(default.longitude_deg)
        self.query_one("#cfg-elev", Input).value = str(default.elevation_m)
        self.query_one("#cfg-lna", Input).value = str(default.default_lna_gain_db)
        self.query_one("#cfg-vga", Input).value = str(default.default_vga_gain_db)
        self.query_one("#cfg-amp", Switch).value = default.default_amplifier
        self.query_one("#cfg-srate", Input).value = str(default.default_sample_rate_msps)
        self.query_one("#cfg-ppm", Input).value = str(default.ppm_correction)
        self.query_one("#cfg-raw-dir", Input).value = default.raw_dir
        self.query_one("#cfg-proc-dir", Input).value = default.processed_dir
        self.query_one("#cfg-tle-h", Input).value = str(default.tle_refresh_hours)

    @work(thread=True)
    def _detect_hardware(self) -> None:
        from satrx.tui.hardware import format_hardware_panel
        hw = detect_hardware()
        freq = 137_700_000.0
        panel = format_hardware_panel(hw, freq)
        self.app.call_from_thread(
            lambda: self.query_one("#hw-status-panel", Static).update(panel)
        )
