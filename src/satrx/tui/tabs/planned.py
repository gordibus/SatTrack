from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

from satrx.tui.hardware import detect_hardware, format_hardware_panel
from satrx.tui.models import AppConfig, PassInfo, ScheduledTask, save_scheduled_tasks


def _freq_label(freq_hz: float) -> str:
    mhz = freq_hz / 1e6
    if mhz < 300:
        return f"{mhz:.3f} MHz [dim](VHF)[/]"
    if mhz < 3000:
        return f"{mhz:.1f} MHz [dim](L/S)[/]"
    return f"{mhz:.1f} MHz [dim](>6GHz)[/]"


def _status_rich(status: str) -> str:
    if status == "en_cours":
        return "[bold #ff00d4]⚙ EN COURS[/]"
    if status == "termine":
        return "[dim #4DC88A]✓ TERMINE[/]"
    if status == "annule":
        return "[dim]✗ ANNULE[/]"
    return "[bold #1EB8A0]⚐ ATTENTE[/]"


class PlannedTab(Vertical):
    DEFAULT_CSS = """
    PlannedTab {
        height: 1fr;
    }
    #tasks-table {
        height: 12;
        border: round #182638;
    }
    #hw-panel {
        height: auto;
        border: round #182638;
        padding: 1 2;
        background: #0D1520;
        margin-top: 1;
    }
    #action-row {
        height: 3;
        padding: 0 1;
    }
    #btn-cancel-task {
        width: 20;
    }
    #btn-refresh-hw {
        width: 22;
        margin-left: 1;
    }
    """

    def __init__(
        self,
        config: AppConfig,
        tasks: list[ScheduledTask],
        tasks_path: Optional[Path] = None,
        on_task_start: Optional[Callable[[ScheduledTask], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._tasks = tasks
        self._tasks_path = tasks_path
        self._on_task_start = on_task_start

    def compose(self) -> ComposeResult:
        yield Label(
            "[bold #1EB8A0]File d'attente des captures programmees[/]",
            id="planned-title",
        )
        yield DataTable(id="tasks-table", cursor_type="row")
        with Horizontal(id="action-row"):
            yield Button("✗ Annuler tache", id="btn-cancel-task", variant="error")
            yield Button("⚙ Actualiser materiel", id="btn-refresh-hw", variant="default")
        yield Static("", id="hw-panel")

    def on_mount(self) -> None:
        table = self.query_one("#tasks-table", DataTable)
        table.add_columns("#", "Satellite", "Debut UTC", "Duree", "Frequence", "Statut")
        self._render_table()
        self._refresh_hardware()
        self.set_interval(30.0, self._tick)

    def _tick(self) -> None:
        self._render_table()
        # Declencher les taches dont l'heure est arrivee
        for task in self._tasks:
            if task.status == "attente" and task.seconds_until_start <= 0:
                task.status = "en_cours"
                if self._on_task_start is not None:
                    self._on_task_start(task)
        self._save()
        self._render_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-task":
            self._cancel_selected()
        elif event.button.id == "btn-refresh-hw":
            self._refresh_hardware()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._refresh_hardware_for_row(event.cursor_row)

    def _cancel_selected(self) -> None:
        table = self.query_one("#tasks-table", DataTable)
        idx = table.cursor_row
        active = [t for t in self._tasks if t.status in ("attente", "en_cours")]
        if 0 <= idx < len(active):
            active[idx].status = "annule"
            self._save()
            self._render_table()

    @work(thread=True)
    def _refresh_hardware(self) -> None:
        hw = detect_hardware()
        table = self.query_one("#tasks-table", DataTable)
        idx = table.cursor_row
        active = [t for t in self._tasks if t.status in ("attente", "en_cours")]
        freq = active[idx].center_freq_hz if 0 <= idx < len(active) else 137_700_000.0
        panel_text = format_hardware_panel(hw, freq)
        self.app.call_from_thread(
            lambda: self.query_one("#hw-panel", Static).update(panel_text)
        )

    def _refresh_hardware_for_row(self, idx: int) -> None:
        active = [t for t in self._tasks if t.status in ("attente", "en_cours")]
        freq = active[idx].center_freq_hz if 0 <= idx < len(active) else 137_700_000.0
        self._refresh_hardware_freq(freq)

    @work(thread=True)
    def _refresh_hardware_freq(self, freq: float) -> None:
        hw = detect_hardware()
        panel_text = format_hardware_panel(hw, freq)
        self.app.call_from_thread(
            lambda: self.query_one("#hw-panel", Static).update(panel_text)
        )

    def _render_table(self) -> None:
        table = self.query_one("#tasks-table", DataTable)
        table.clear()
        visible = [t for t in self._tasks if t.status in ("attente", "en_cours")]
        for i, task in enumerate(visible, 1):
            start_str = task.start_utc.strftime("%H:%M:%S")
            mm, ss = divmod(int(task.duration_s), 60)
            dur = f"{mm}m{ss:02d}s"
            freq_str = f"{task.center_freq_hz / 1e6:.3f} MHz"
            table.add_row(
                str(i),
                task.satellite_name,
                start_str,
                dur,
                freq_str,
                _status_rich(task.status),
            )

    def add_task_from_pass(self, p: PassInfo, config: AppConfig) -> ScheduledTask:
        """Cree et ajoute une tache planifiee a partir d'un PassInfo."""
        freq_hz = _guess_freq_hz(p.satellite_name)
        task = ScheduledTask(
            task_id=str(uuid.uuid4())[:8],
            satellite_name=p.satellite_name,
            norad_id=p.norad_id,
            start_utc=p.aos_utc,
            duration_s=p.duration_s,
            center_freq_hz=freq_hz,
            sample_rate_hz=config.default_sample_rate_msps * 1e6,
            lna_gain_db=config.default_lna_gain_db,
            vga_gain_db=config.default_vga_gain_db,
            amplifier=config.default_amplifier,
        )
        self._tasks.append(task)
        self._save()
        self._render_table()
        return task

    def _save(self) -> None:
        if self._tasks_path is not None:
            save_scheduled_tasks(self._tasks_path, self._tasks)


def _guess_freq_hz(satellite_name: str) -> float:
    """
    Frequence centrale par defaut a partir du nom du satellite.
    Desaccord de 200 kHz par rapport a la frequence nominale (PPM HackRF +300 ppm,
    cf. CONTEXT.md : centrer a 137.7 MHz pour Meteor-M2 emettant a 137.9 MHz).
    """
    name = satellite_name.upper()
    if "METEOR" in name:
        return 137_700_000.0   # visee 137.9 MHz, desaccord -200 kHz
    if "NOAA 15" in name:
        return 137_500_000.0   # visee 137.62 MHz
    if "NOAA 18" in name:
        return 137_700_000.0   # visee 137.912 MHz
    if "NOAA 19" in name:
        return 137_100_000.0   # visee 137.1 MHz
    if "ISS" in name or "ZARYA" in name:
        return 145_800_000.0
    if "IRIDIUM" in name:
        return 1_621_250_000.0
    return 137_700_000.0
