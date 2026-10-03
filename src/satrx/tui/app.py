from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Log, Static

from satrx.acquisition.params import RecordingParams, SdrDevice
from satrx.acquisition.recorder import (
    parse_hackrf_stats_line,
    start_recording_process,
    write_metadata_sidecar,
)
from satrx.tracking.passes import TrajectoryPoint
from satrx.tui.satellite_widget import SatelliteSkyWidget

CYBERPUNK_CSS = """
Screen {
    background: #05050a;
    color: #00fff2;
}

Header {
    background: #0a0a14;
    color: #ff00d4;
}

Footer {
    background: #0a0a14;
}

#status-panel {
    height: auto;
    border: round #ff00d4;
    padding: 1 2;
    background: #0a0a14;
    color: #00fff2;
}

#stats-panel {
    height: auto;
    border: round #00fff2;
    padding: 1 2;
    background: #0a0a14;
    color: #ff00d4;
}

Log {
    border: round #1a6b66;
    background: #05050a;
    color: #0dd3c4;
}
"""


@dataclass(frozen=True)
class CapturePlan:
    satellite_name: str
    device: SdrDevice
    center_freq_hz: float
    sample_rate_hz: float
    duration_s: float
    lna_gain_db: float | None
    gain_db: float | None
    amplifier_enabled: bool
    start_at_utc: datetime
    output_dir: Path
    trajectory: list[TrajectoryPoint]

    @staticmethod
    def from_json_file(path: Path) -> "CapturePlan":
        data = json.loads(path.read_text())
        return CapturePlan(
            satellite_name=data["satellite_name"],
            device=SdrDevice(data["device"]),
            center_freq_hz=data["center_freq_hz"],
            sample_rate_hz=data["sample_rate_hz"],
            duration_s=data["duration_s"],
            lna_gain_db=data.get("lna_gain_db"),
            gain_db=data.get("gain_db"),
            amplifier_enabled=data.get("amplifier_enabled", False),
            start_at_utc=datetime.fromisoformat(data["start_at_utc"]),
            output_dir=Path(data["output_dir"]),
            trajectory=[
                TrajectoryPoint(
                    seconds_from_start=p["seconds_from_start"],
                    elevation_deg=p["elevation_deg"],
                    azimuth_deg=p["azimuth_deg"],
                )
                for p in data["trajectory"]
            ],
        )


class SatRxCaptureApp(App[None]):
    TITLE = "SatRX - capture programmee"
    CSS = CYBERPUNK_CSS
    BINDINGS = [("q", "quit", "Quitter")]

    phase: reactive[str] = reactive("attente")
    countdown_s: reactive[float] = reactive(0.0)
    elapsed_record_s: reactive[float] = reactive(0.0)
    last_power_dbfs: reactive[float | None] = reactive(None)

    def __init__(self, plan: CapturePlan) -> None:
        super().__init__()
        self._plan = plan

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static(id="status-panel")
            yield SatelliteSkyWidget(self._plan.trajectory, id="sky")
            yield Static(id="stats-panel")
            yield Log(id="log", highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)
        self._run_capture()

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        if self.phase == "attente":
            self.countdown_s = max((self._plan.start_at_utc - now).total_seconds(), 0.0)
        elif self.phase == "enregistrement":
            self.elapsed_record_s = (now - self._plan.start_at_utc).total_seconds()
            self.query_one(SatelliteSkyWidget).elapsed_s = self.elapsed_record_s
            self.query_one(SatelliteSkyWidget).active = True
        self._refresh_panels()

    def _refresh_panels(self) -> None:
        status = self.query_one("#status-panel", Static)
        stats = self.query_one("#stats-panel", Static)

        if self.phase == "attente":
            mm, ss = divmod(int(self.countdown_s), 60)
            hh, mm = divmod(mm, 60)
            status.update(
                f"[bold]SATELLITE[/] {self._plan.satellite_name}   "
                f"[bold]STATUT[/] EN ATTENTE\n"
                f"[bold]DEBUT PROGRAMME[/] {self._plan.start_at_utc.astimezone().strftime('%H:%M:%S')}   "
                f"[bold]COMPTE A REBOURS[/] {hh:02d}:{mm:02d}:{ss:02d}"
            )
        elif self.phase == "enregistrement":
            remaining = max(self._plan.duration_s - self.elapsed_record_s, 0.0)
            mm, ss = divmod(int(self.elapsed_record_s), 60)
            rmm, rss = divmod(int(remaining), 60)
            status.update(
                f"[bold]SATELLITE[/] {self._plan.satellite_name}   "
                f"[bold]STATUT[/] [bold #ff00d4]ENREGISTREMENT EN COURS[/]\n"
                f"[bold]ECOULE[/] {mm:02d}:{ss:02d}   [bold]RESTANT[/] {rmm:02d}:{rss:02d}"
            )
        else:
            status.update(f"[bold]SATELLITE[/] {self._plan.satellite_name}   [bold]STATUT[/] TERMINE")

        power = f"{self.last_power_dbfs:.1f} dBfs" if self.last_power_dbfs is not None else "-"
        stats.update(
            f"[bold]Frequence[/] {self._plan.center_freq_hz / 1e6:.3f} MHz   "
            f"[bold]Sample rate[/] {self._plan.sample_rate_hz / 1e6:.3f} Msps   "
            f"[bold]Duree[/] {self._plan.duration_s:.0f}s\n"
            f"[bold]Puissance moyenne[/] {power}"
        )

    @work(exclusive=True, thread=False)
    async def _run_capture(self) -> None:
        log = self.query_one(Log)
        now = datetime.now(timezone.utc)
        wait_s = (self._plan.start_at_utc - now).total_seconds()
        if wait_s > 0:
            log.write_line(f"En attente de {self._plan.start_at_utc.isoformat()} ({wait_s:.0f}s)")
            await asyncio.sleep(wait_s)

        self.phase = "enregistrement"
        params = RecordingParams(
            satellite_name=self._plan.satellite_name,
            center_freq_hz=self._plan.center_freq_hz,
            sample_rate_hz=self._plan.sample_rate_hz,
            duration_s=self._plan.duration_s,
            gain_db=self._plan.gain_db,
            lna_gain_db=self._plan.lna_gain_db,
            amplifier_enabled=self._plan.amplifier_enabled,
        )
        process, metadata, output_path = start_recording_process(
            self._plan.device, params, self._plan.output_dir
        )
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
                self.last_power_dbfs = stats.average_power_dbfs

        process.wait()
        write_metadata_sidecar(metadata, output_path.with_suffix(output_path.suffix + ".json"))
        self.phase = "termine"
        self.query_one(SatelliteSkyWidget).active = False
        log.write_line(f"Termine. Fichier : {output_path}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m satrx.tui.app <plan.json>", file=sys.stderr)
        raise SystemExit(1)
    plan = CapturePlan.from_json_file(Path(sys.argv[1]))
    SatRxCaptureApp(plan).run()


if __name__ == "__main__":
    main()
