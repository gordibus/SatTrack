from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Log, Static

from satrx.tui.models import AppConfig, ScheduledTask
from satrx.tui.satellite_widget import SatelliteSkyWidget
from satrx.tracking.passes import TrajectoryPoint


class ActiveTab(Vertical):
    DEFAULT_CSS = """
    ActiveTab {
        height: 1fr;
    }
    #active-status {
        height: 3;
        border: round #ff00d4;
        padding: 0 2;
        background: #0a0a14;
    }
    #active-stats {
        height: 3;
        border: round #00fff2;
        padding: 0 2;
        background: #0a0a14;
    }
    #sky-active {
        height: 13;
    }
    #active-log {
        height: 1fr;
        border: round #1a6b66;
        background: #05050a;
        color: #0dd3c4;
    }
    #active-actions {
        height: 3;
        padding: 0 1;
    }
    #btn-decode-after {
        width: 30;
    }
    #btn-abort {
        width: 22;
        margin-left: 1;
    }
    #idle-panel {
        height: 1fr;
        padding: 2 4;
        color: #4A6A82;
    }
    """

    _current_task: reactive[Optional[ScheduledTask]] = reactive(None)
    _elapsed_s: reactive[float] = reactive(0.0)
    _power_dbfs: reactive[Optional[float]] = reactive(None)
    _doppler_hz: reactive[Optional[float]] = reactive(None)
    _auto_decode: reactive[bool] = reactive(False)

    def __init__(
        self,
        config: AppConfig,
        raw_dir: Path,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._raw_dir = raw_dir
        self._trajectory: list[TrajectoryPoint] = []

    def compose(self) -> ComposeResult:
        yield Static("Aucune capture active.", id="idle-panel")
        yield Static("", id="active-status")
        yield SatelliteSkyWidget([], id="sky-active")
        yield Static("", id="active-stats")
        with Horizontal(id="active-actions"):
            yield Button("⚙ Decoder a la fin", id="btn-decode-after", variant="primary")
            yield Button("✗ Annuler la capture", id="btn-abort", variant="error")
        yield Log(id="active-log", highlight=False)

    def on_mount(self) -> None:
        self._show_idle()
        self.set_interval(1.0, self._tick)

    def _show_idle(self) -> None:
        self.query_one("#idle-panel").display = True
        self.query_one("#active-status").display = False
        self.query_one("#sky-active").display = False
        self.query_one("#active-stats").display = False
        self.query_one("#active-actions").display = False
        self.query_one("#active-log").display = False

    def _show_active(self) -> None:
        self.query_one("#idle-panel").display = False
        self.query_one("#active-status").display = True
        self.query_one("#sky-active").display = True
        self.query_one("#active-stats").display = True
        self.query_one("#active-actions").display = True
        self.query_one("#active-log").display = True

    def start_task(self, task: ScheduledTask) -> None:
        self._current_task = task
        self._elapsed_s = 0.0
        self._power_dbfs = None
        self._auto_decode = False
        self._trajectory = self._compute_trajectory(task)
        sky = self.query_one("#sky-active", SatelliteSkyWidget)
        sky._trajectory = self._trajectory
        sky._total_s = self._trajectory[-1].seconds_from_start if self._trajectory else 1.0
        sky._max_elevation = max((p.elevation_deg for p in self._trajectory), default=1.0)
        sky.elapsed_s = 0.0
        sky.active = True
        self._show_active()
        self._run_capture_worker(task)

    def _compute_trajectory(self, task: ScheduledTask) -> list[TrajectoryPoint]:
        try:
            from skyfield.api import load as sf_load
            from satrx.tracking.passes import compute_trajectory
            from satrx.tracking.station import GroundStation
            from satrx.tracking.tle import fetch_tle_celestrak

            ts = sf_load.timescale()
            station = GroundStation(
                name=self._config.station_name,
                latitude_deg=self._config.latitude_deg,
                longitude_deg=self._config.longitude_deg,
                elevation_m=self._config.elevation_m,
            )
            sat = fetch_tle_celestrak(task.norad_id, timeout_s=8.0)
            t_start = ts.from_datetime(task.start_utc)
            return compute_trajectory(sat, station, t_start, task.duration_s, n_samples=120)
        except Exception:
            return []

    def _tick(self) -> None:
        task = self._current_task
        if task is None:
            return
        now = datetime.now(timezone.utc)
        self._elapsed_s = max((now - task.start_utc).total_seconds(), 0.0)
        sky = self.query_one("#sky-active", SatelliteSkyWidget)
        sky.elapsed_s = self._elapsed_s
        self._update_doppler(task)
        self._refresh_panels(task)

    def _update_doppler(self, task: ScheduledTask) -> None:
        try:
            from skyfield.api import load as sf_load
            from satrx.tracking.doppler import doppler_shift_hz
            from satrx.tracking.station import GroundStation
            from satrx.tracking.tle import fetch_tle_celestrak

            ts = sf_load.timescale()
            station = GroundStation(
                name=self._config.station_name,
                latitude_deg=self._config.latitude_deg,
                longitude_deg=self._config.longitude_deg,
                elevation_m=self._config.elevation_m,
            )
            sat = fetch_tle_celestrak(task.norad_id, timeout_s=3.0)
            t_now = ts.from_datetime(datetime.now(timezone.utc))
            nominal = task.center_freq_hz + 200_000.0  # freq nominale estimee
            self._doppler_hz = doppler_shift_hz(sat, station, t_now, nominal)
        except Exception:
            pass

    def _refresh_panels(self, task: ScheduledTask) -> None:
        elapsed = self._elapsed_s
        remaining = max(task.duration_s - elapsed, 0.0)
        em, es = divmod(int(elapsed), 60)
        rm, rs = divmod(int(remaining), 60)
        status = self.query_one("#active-status", Static)
        status.update(
            f"[bold]SATELLITE[/] {task.satellite_name}   "
            f"[bold #ff00d4]ENREGISTREMENT EN COURS[/]\n"
            f"[bold]ECOULE[/] {em:02d}:{es:02d}   "
            f"[bold]RESTANT[/] {rm:02d}:{rs:02d}   "
            f"[bold]TACHE[/] {task.task_id}"
        )
        pwr = f"{self._power_dbfs:.1f} dBfs" if self._power_dbfs is not None else "-"
        dop = f"{self._doppler_hz/1000:+.2f} kHz" if self._doppler_hz is not None else "-"
        stats = self.query_one("#active-stats", Static)
        stats.update(
            f"[bold]Freq centre[/] {task.center_freq_hz/1e6:.3f} MHz   "
            f"[bold]Puissance[/] {pwr}   "
            f"[bold]Doppler[/] {dop}"
        )

    @work(exclusive=True, thread=False)
    async def _run_capture_worker(self, task: ScheduledTask) -> None:
        from satrx.acquisition.params import RecordingParams, SdrDevice
        from satrx.acquisition.recorder import (
            parse_hackrf_stats_line,
            start_recording_process,
            write_metadata_sidecar,
        )

        log = self.query_one(Log)
        params = RecordingParams(
            satellite_name=task.satellite_name,
            center_freq_hz=task.center_freq_hz,
            sample_rate_hz=task.sample_rate_hz,
            duration_s=task.duration_s,
            gain_db=task.vga_gain_db,
            lna_gain_db=task.lna_gain_db,
            amplifier_enabled=task.amplifier,
        )
        process, metadata, output_path = start_recording_process(
            SdrDevice.HACKRF, params, self._raw_dir
        )
        task.output_file = str(output_path)
        log.write_line(f"Enregistrement demarre -> {output_path}")

        assert process.stdout is not None
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line:
                break
            log.write_line(line.rstrip())
            stats = parse_hackrf_stats_line(line)
            if stats is not None:
                self._power_dbfs = stats.average_power_dbfs

        process.wait()
        write_metadata_sidecar(metadata, output_path.with_suffix(output_path.suffix + ".json"))
        task.status = "termine"
        sky = self.query_one("#sky-active", SatelliteSkyWidget)
        sky.active = False
        log.write_line(f"✓ Termine. Fichier : {output_path}")

        if self._auto_decode and task.output_file:
            self.app.notify(f"Capture terminee - lancement du decodage de {output_path.name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-decode-after":
            self._auto_decode = not self._auto_decode
            label = "✓ Decoder a la fin (ON)" if self._auto_decode else "⚙ Decoder a la fin"
            event.button.label = label
        elif event.button.id == "btn-abort":
            if self._current_task is not None:
                self._current_task.status = "annule"
                self._current_task = None
                self._show_idle()
