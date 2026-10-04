from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
from satrx.tracking.passes import TrajectoryPoint, interpolate_azel
from satrx.tui.satellite_widget import SatelliteSkyWidget

_GOTO_INTERVAL_S: float = 5.0

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

#rotator-panel {
    height: auto;
    border: round #1a6b66;
    padding: 1 2;
    background: #0a0a14;
    color: #0dd3c4;
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
    lna_gain_db: Optional[float]
    gain_db: Optional[float]
    amplifier_enabled: bool
    start_at_utc: datetime
    output_dir: Path
    trajectory: list[TrajectoryPoint]
    # coordonnees observateur (pour la conversion AZ/EL -> AR/Dec du rotateur)
    observer_lat: float = 48.9101
    observer_lon: float = 2.2549
    # pointage automatique : port serie EXOS-II (None = pas de rotateur)
    rotator_port: Optional[str] = None
    # simulation : True = pas de SDR ni de serie, acceleration temporelle
    simulate: bool = False
    sim_speed: float = 20.0

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
            observer_lat=data.get("observer_lat", 48.9101),
            observer_lon=data.get("observer_lon", 2.2549),
            rotator_port=data.get("rotator_port"),
        )


class SatRxCaptureApp(App[None]):
    TITLE = "SatRX - capture programmee"
    CSS = CYBERPUNK_CSS
    BINDINGS = [("q", "quit", "Quitter")]

    phase: reactive[str] = reactive("attente")
    countdown_s: reactive[float] = reactive(0.0)
    elapsed_record_s: reactive[float] = reactive(0.0)
    last_power_dbfs: reactive[Optional[float]] = reactive(None)
    tracking_azel: reactive[Optional[tuple[float, float]]] = reactive(None)
    rotator_status: reactive[str] = reactive("")

    def __init__(self, plan: CapturePlan) -> None:
        super().__init__()
        self._plan = plan

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static(id="status-panel")
            yield SatelliteSkyWidget(self._plan.trajectory, id="sky")
            yield Static(id="stats-panel")
            if self._plan.rotator_port is not None or self._plan.simulate:
                yield Static(id="rotator-panel")
            yield Log(id="log", highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)
        self._run_capture()
        if self._plan.rotator_port is not None or self._plan.simulate:
            self._run_tracking()

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        if self.phase == "attente":
            if self._plan.simulate:
                self.countdown_s = 0.0
            else:
                self.countdown_s = max((self._plan.start_at_utc - now).total_seconds(), 0.0)
        elif self.phase == "enregistrement":
            if self._plan.simulate:
                self.elapsed_record_s = min(
                    self.elapsed_record_s + self._plan.sim_speed,
                    self._plan.duration_s,
                )
            else:
                self.elapsed_record_s = (now - self._plan.start_at_utc).total_seconds()
            self.query_one(SatelliteSkyWidget).elapsed_s = self.elapsed_record_s
            self.query_one(SatelliteSkyWidget).active = True
        self._refresh_panels()

    def _refresh_panels(self) -> None:
        status = self.query_one("#status-panel", Static)
        stats = self.query_one("#stats-panel", Static)

        sim_tag = " [bold #ff6600][SIM][/]" if self._plan.simulate else ""

        if self.phase == "attente":
            mm, ss = divmod(int(self.countdown_s), 60)
            hh, mm = divmod(mm, 60)
            status.update(
                f"[bold]SATELLITE[/] {self._plan.satellite_name}{sim_tag}   "
                f"[bold]STATUT[/] EN ATTENTE\n"
                f"[bold]DEBUT PROGRAMME[/] {self._plan.start_at_utc.astimezone().strftime('%H:%M:%S')}   "
                f"[bold]COMPTE A REBOURS[/] {hh:02d}:{mm:02d}:{ss:02d}"
            )
        elif self.phase == "enregistrement":
            remaining = max(self._plan.duration_s - self.elapsed_record_s, 0.0)
            mm, ss = divmod(int(self.elapsed_record_s), 60)
            rmm, rss = divmod(int(remaining), 60)
            status.update(
                f"[bold]SATELLITE[/] {self._plan.satellite_name}{sim_tag}   "
                f"[bold]STATUT[/] [bold #ff00d4]ENREGISTREMENT EN COURS[/]\n"
                f"[bold]ECOULE[/] {mm:02d}:{ss:02d}   [bold]RESTANT[/] {rmm:02d}:{rss:02d}"
            )
        else:
            status.update(
                f"[bold]SATELLITE[/] {self._plan.satellite_name}{sim_tag}   [bold]STATUT[/] TERMINE"
            )

        power = f"{self.last_power_dbfs:.1f} dBfs" if self.last_power_dbfs is not None else "-"
        stats.update(
            f"[bold]Frequence[/] {self._plan.center_freq_hz / 1e6:.3f} MHz   "
            f"[bold]Sample rate[/] {self._plan.sample_rate_hz / 1e6:.3f} Msps   "
            f"[bold]Duree[/] {self._plan.duration_s:.0f}s\n"
            f"[bold]Puissance moyenne[/] {power}"
        )

        try:
            rotator_panel = self.query_one("#rotator-panel", Static)
        except Exception:
            return

        if self.tracking_azel is not None:
            az, el = self.tracking_azel
            port_label = self._plan.rotator_port or "(sim)"
            status_label = self.rotator_status or "-"
            rotator_panel.update(
                f"[bold]ROTATEUR[/] {port_label}   "
                f"[bold]CIBLE[/] AZ {az:.1f} deg  EL {el:.1f} deg   "
                f"[bold]REPONSE[/] {status_label}"
            )
        else:
            rotator_panel.update("[bold]ROTATEUR[/] en attente du passage...")

    @work(exclusive=True, thread=False)
    async def _run_capture(self) -> None:
        log = self.query_one(Log)

        if self._plan.simulate:
            log.write_line(
                f"[SIMULATION x{self._plan.sim_speed:.0f}] Debut immediat "
                f"(duree reelle : {self._plan.duration_s / self._plan.sim_speed:.0f}s)"
            )
        else:
            now = datetime.now(timezone.utc)
            wait_s = (self._plan.start_at_utc - now).total_seconds()
            if wait_s > 0:
                log.write_line(
                    f"En attente de {self._plan.start_at_utc.isoformat()} ({wait_s:.0f}s)"
                )
                await asyncio.sleep(wait_s)

        self.phase = "enregistrement"

        if self._plan.simulate:
            real_duration = self._plan.duration_s / self._plan.sim_speed
            log.write_line(
                f"[SIMULATION] Passage simule sur {real_duration:.0f}s reelles "
                f"({self._plan.duration_s:.0f}s satellite)"
            )
            await asyncio.sleep(real_duration)
        else:
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
            log.write_line(f"Termine. Fichier : {output_path}")

        self.phase = "termine"
        self.query_one(SatelliteSkyWidget).active = False
        if self._plan.simulate:
            log.write_line("[SIMULATION] Passage termine.")

    @work(exclusive=False, thread=False)
    async def _run_tracking(self) -> None:
        """Boucle de pointage automatique EXOS-II pendant le passage.

        En mode simulation (rotator_port=None et simulate=True) : log les commandes
        sans ouvrir de port serie, pour verifier la trajectoire de pointage.
        En mode reel (rotator_port defini) : envoie les trames GOTO toutes les
        _GOTO_INTERVAL_S secondes via le port serie.
        """
        from satrx.antenna.exos2_backend import ExosIIBackend

        log = self.query_one(Log)

        # Attendre le debut de l'enregistrement
        while self.phase == "attente":
            await asyncio.sleep(0.25)

        if self.phase == "termine":
            return

        use_serial = self._plan.rotator_port is not None and not self._plan.simulate
        backend: Optional[ExosIIBackend] = None

        if use_serial:
            backend = ExosIIBackend(
                self._plan.rotator_port,  # type: ignore[arg-type]
                observer_lat=self._plan.observer_lat,
                observer_lon=self._plan.observer_lon,
            )
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, backend.connect)
                log.write_line("✓ Rotateur EXOS-II connecte")
            except Exception as exc:
                log.write_line(f"✖ Rotateur : connexion echouee ({exc})")
                self.rotator_status = "ERREUR connexion"
                return
        elif self._plan.simulate:
            log.write_line("[SIMULATION] Pointage rotateur (serie desactive)")

        try:
            while self.phase == "enregistrement":
                elapsed = self.elapsed_record_s
                try:
                    az, el = interpolate_azel(self._plan.trajectory, elapsed)
                    self.tracking_azel = (az, el)

                    if el < 5.0:
                        self.rotator_status = f"attente elevation ({el:.1f} deg)"
                    else:
                        cmd = f"AZ{az:.1f} EL{el:.1f}"
                        if use_serial and backend is not None:
                            result = await asyncio.get_running_loop().run_in_executor(
                                None, backend.send_command, cmd
                            )
                        else:
                            result = "OK (sim)"
                        self.rotator_status = result
                        log.write_line(f"GOTO {cmd} -> {result}")
                except Exception as exc:
                    self.rotator_status = f"ERROR:{exc}"
                    log.write_line(f"✖ Tracking erreur : {exc}")

                # intervalle adapte au mode sim pour couvrir toute la trajectoire
                if self._plan.simulate:
                    await asyncio.sleep(max(0.5, _GOTO_INTERVAL_S / self._plan.sim_speed))
                else:
                    await asyncio.sleep(_GOTO_INTERVAL_S)
        finally:
            if use_serial and backend is not None:
                await asyncio.get_running_loop().run_in_executor(None, backend.disconnect)
                log.write_line("Rotateur deconnecte")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SatRX - TUI de capture programmee")
    parser.add_argument("plan", help="chemin vers le fichier plan JSON")
    parser.add_argument(
        "--rotator-port",
        default=None,
        metavar="PORT",
        help="port serie EXOS-II pour le pointage automatique (ex: /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="mode simulation : pas de SDR ni de serie, acceleration temporelle",
    )
    parser.add_argument(
        "--sim-speed",
        type=float,
        default=20.0,
        metavar="N",
        help="facteur d'acceleration en mode simulation (defaut 20, soit 826s -> 41s reelles)",
    )
    args = parser.parse_args()

    plan = CapturePlan.from_json_file(Path(args.plan))
    plan = dataclasses.replace(
        plan,
        rotator_port=args.rotator_port if args.rotator_port else plan.rotator_port,
        simulate=args.simulate or plan.simulate,
        sim_speed=args.sim_speed,
    )
    SatRxCaptureApp(plan).run()


if __name__ == "__main__":
    main()
