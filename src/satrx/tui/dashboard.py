from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, TabbedContent, TabPane

from satrx.tui.models import (
    AppConfig,
    FavoriteEntry,
    ScheduledTask,
    load_config,
    load_favorites,
    load_scheduled_tasks,
    save_scheduled_tasks,
)
from satrx.tui.tabs.passes import PassesTab
from satrx.tui.tabs.planned import PlannedTab
from satrx.tui.tabs.active import ActiveTab
from satrx.tui.tabs.decode import DecodeTab
from satrx.tui.tabs.security import SecurityTab
from satrx.tui.tabs.archives import ArchivesTab
from satrx.tui.tabs.config import ConfigTab


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

DASHBOARD_CSS = """
Screen {
    background: #05050a;
    color: #C8DFF0;
}

Header {
    background: #0a0a14;
    color: #ff00d4;
}

Footer {
    background: #0a0a14;
    color: #4A6A82;
}

TabbedContent {
    height: 1fr;
}

TabbedContent > Tabs {
    background: #0a0a14;
}

TabbedContent > Tabs > Tab {
    color: #4A6A82;
}

TabbedContent > Tabs > Tab.-active {
    color: #1EB8A0;
    border-bottom: tall #1EB8A0;
}

TabPane {
    background: #05050a;
    padding: 0;
}

Button {
    background: #0D1520;
    border: tall #182638;
    color: #C8DFF0;
}

Button.-primary {
    background: #0D2A2A;
    border: tall #1EB8A0;
    color: #1EB8A0;
}

Button.-success {
    background: #0D2A1A;
    border: tall #4DC88A;
    color: #4DC88A;
}

Button.-error {
    background: #2A0D0D;
    border: tall #E05050;
    color: #E05050;
}

Button.-warning {
    background: #2A1D0D;
    border: tall #E2934A;
    color: #E2934A;
}

Input {
    background: #0D1520;
    border: tall #182638;
    color: #C8DFF0;
}

Input:focus {
    border: tall #1EB8A0;
}

Select {
    background: #0D1520;
    border: tall #182638;
    color: #C8DFF0;
}

DataTable {
    background: #05050a;
    color: #C8DFF0;
}

DataTable > .datatable--header {
    background: #0D1520;
    color: #1EB8A0;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #182638;
    color: #5EFBD3;
}

Switch.-on {
    background: #1EB8A0;
}

Label {
    color: #C8DFF0;
}
"""


class SatRxDashboard(App[None]):
    TITLE = "SatRX Dashboard"
    CSS = DASHBOARD_CSS

    BINDINGS = [
        Binding("1", "switch_tab('passes')",   "Passes",    show=True),
        Binding("2", "switch_tab('planned')",  "Planifié",  show=True),
        Binding("3", "switch_tab('active')",   "En cours",  show=True),
        Binding("4", "switch_tab('decode')",   "Decodage",  show=True),
        Binding("5", "switch_tab('security')", "Securite",  show=True),
        Binding("6", "switch_tab('archives')", "Archives",  show=True),
        Binding("7", "switch_tab('config')",   "Config",    show=True),
        Binding("f", "toggle_favorite",        "Favori",    show=False),
        Binding("r", "refresh_tle",            "TLE",       show=False),
        Binding("q", "quit_confirm",           "Quitter",   show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        data_dir = _PROJECT_ROOT / "data"
        self._config_path   = data_dir / "config.json"
        self._favorites_path = data_dir / "favorites.json"
        self._tasks_path    = data_dir / "scheduled_tasks.json"

        self._config: AppConfig = load_config(self._config_path)
        self._favorites: list[FavoriteEntry] = load_favorites(self._favorites_path)
        self._tasks: list[ScheduledTask] = load_scheduled_tasks(self._tasks_path)

        self._raw_dir = _PROJECT_ROOT / self._config.raw_dir
        self._processed_dir = _PROJECT_ROOT / self._config.processed_dir

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent(id="main-tabs", initial="passes"):
            with TabPane("1 PASSES", id="passes"):
                yield PassesTab(
                    config=self._config,
                    favorites=self._favorites,
                    favorites_path=self._favorites_path,
                    id="tab-passes",
                )
            with TabPane("2 PLANIFIÉ", id="planned"):
                yield PlannedTab(
                    config=self._config,
                    tasks=self._tasks,
                    tasks_path=self._tasks_path,
                    on_task_start=self._on_task_start,
                    id="tab-planned",
                )
            with TabPane("3 EN COURS", id="active"):
                yield ActiveTab(
                    config=self._config,
                    raw_dir=self._raw_dir,
                    id="tab-active",
                )
            with TabPane("4 DÉCODAGE", id="decode"):
                yield DecodeTab(
                    raw_dir=self._raw_dir,
                    processed_dir=self._processed_dir,
                    id="tab-decode",
                )
            with TabPane("5 SÉCURITÉ", id="security"):
                yield SecurityTab(
                    raw_dir=self._raw_dir,
                    processed_dir=self._processed_dir,
                    id="tab-security",
                )
            with TabPane("6 ARCHIVES", id="archives"):
                yield ArchivesTab(
                    raw_dir=self._raw_dir,
                    processed_dir=self._processed_dir,
                    on_decode=self._goto_decode,
                    on_security=self._goto_security,
                    id="tab-archives",
                )
            with TabPane("7 CONFIG", id="config"):
                yield ConfigTab(
                    config=self._config,
                    config_path=self._config_path,
                    id="tab-config",
                )

        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(60.0, self._tick_tasks)

    def _tick_tasks(self) -> None:
        for task in self._tasks:
            if task.status == "attente" and task.seconds_until_start <= 60:
                self.notify(
                    f"Capture dans moins d'1 minute : {task.satellite_name}",
                    severity="warning",
                )
            if task.status == "attente" and task.seconds_until_start <= 0:
                self._on_task_start(task)
        save_scheduled_tasks(self._tasks_path, self._tasks)

    def _on_task_start(self, task: ScheduledTask) -> None:
        task.status = "en_cours"
        active_tab = self.query_one("#tab-active", ActiveTab)
        active_tab.start_task(task)
        tc = self.query_one("#main-tabs", TabbedContent)
        tc.active = "active"
        save_scheduled_tasks(self._tasks_path, self._tasks)

    # ------------------------------------------------------------------ #
    # Navigation inter-onglets depuis les onglets enfants
    # ------------------------------------------------------------------ #

    def _goto_decode(self, path: Path) -> None:
        self.query_one("#tab-decode", DecodeTab).preselect_file(path)
        self.query_one("#main-tabs", TabbedContent).active = "decode"

    def _goto_security(self, path: Path) -> None:
        tc = self.query_one("#main-tabs", TabbedContent)
        tc.active = "security"

    # ------------------------------------------------------------------ #
    # Depuis l'onglet Passes : Entrée → planifier une capture
    # ------------------------------------------------------------------ #

    def on_data_table_row_selected(self, event: "DataTable.RowSelected") -> None:
        tc = self.query_one("#main-tabs", TabbedContent)
        if tc.active != "passes":
            return
        passes_tab = self.query_one("#tab-passes", PassesTab)
        selected = passes_tab.get_selected_pass()
        if selected is None:
            return
        planned_tab = self.query_one("#tab-planned", PlannedTab)
        planned_tab.add_task_from_pass(selected, self._config)
        self.notify(
            f"Tache planifiee : {selected.satellite_name} a "
            f"{selected.aos_utc.strftime('%H:%M UTC')}",
        )
        tc.active = "planned"

    # ------------------------------------------------------------------ #
    # Actions globales (touches)
    # ------------------------------------------------------------------ #

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#main-tabs", TabbedContent).active = tab_id

    def action_toggle_favorite(self) -> None:
        tc = self.query_one("#main-tabs", TabbedContent)
        if tc.active == "passes":
            self.query_one("#tab-passes", PassesTab).action_toggle_favorite()

    def action_refresh_tle(self) -> None:
        tc = self.query_one("#main-tabs", TabbedContent)
        if tc.active == "passes":
            self.query_one("#tab-passes", PassesTab)._load_passes()

    def action_quit_confirm(self) -> None:
        active = [t for t in self._tasks if t.status == "en_cours"]
        if active:
            self.notify(
                f"Capture en cours ({active[0].satellite_name}) - appuyer a nouveau sur q pour forcer.",
                severity="warning",
            )
        else:
            self.exit()


def main() -> None:
    SatRxDashboard().run()


if __name__ == "__main__":
    main()
