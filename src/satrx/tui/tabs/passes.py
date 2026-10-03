from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, Label

from satrx.tui.models import (
    AppConfig,
    FavoriteEntry,
    PassInfo,
    KNOWN_SATELLITES,
    save_favorites,
)

if TYPE_CHECKING:
    pass


def _format_countdown(seconds: float) -> str:
    if seconds <= 0:
        return "maintenant"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def _elev_style(elev: float) -> str:
    if elev >= 50.0:
        return "bold #4DC88A"
    if elev >= 20.0:
        return "bold #E2934A"
    return "dim #7A7A7A"


class PassesTab(Vertical):
    DEFAULT_CSS = """
    PassesTab {
        height: 1fr;
    }
    #search-row {
        height: 3;
        padding: 0 1;
    }
    #sort-row {
        height: 3;
        padding: 0 1;
    }
    #search-input {
        width: 1fr;
    }
    #btn-search {
        width: 14;
        margin-left: 1;
    }
    #btn-refresh-tle {
        width: 10;
        margin-left: 1;
    }
    #btn-sort-pass {
        width: 22;
    }
    #btn-sort-alpha {
        width: 16;
        margin-left: 1;
    }
    #status-label {
        height: 1;
        padding: 0 1;
        color: #4A6A82;
    }
    #passes-table {
        height: 1fr;
        border: round #182638;
    }
    """

    _sort_by_time: reactive[bool] = reactive(True)
    _passes: reactive[list[PassInfo]] = reactive([], layout=True)
    _status_msg: reactive[str] = reactive("")

    def __init__(
        self,
        config: AppConfig,
        favorites: list[FavoriteEntry],
        favorites_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._favorites = favorites
        self._favorites_path = favorites_path

    def compose(self) -> ComposeResult:
        with Horizontal(id="search-row"):
            yield Input(placeholder="Nom ou NORAD ID (ex: METEOR-M2 3, 57166)", id="search-input")
            yield Button("Chercher", id="btn-search", variant="primary")
            yield Button("TLE [r]", id="btn-refresh-tle", variant="default")
        with Horizontal(id="sort-row"):
            yield Label("Trier : ", classes="sort-label")
            yield Button("◆ Prochain passage", id="btn-sort-pass", variant="success")
            yield Button("A→Z Nom", id="btn-sort-alpha", variant="default")
        yield Label("", id="status-label")
        yield DataTable(id="passes-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#passes-table", DataTable)
        table.add_columns("★", "Satellite", "AOS UTC", "Dans", "Durée", "Elev max", "ID")
        self._load_passes()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-search":
            self._do_search()
        elif event.button.id == "btn-refresh-tle":
            self._load_passes()
        elif event.button.id == "btn-sort-pass":
            self._sort_by_time = True
            self._render_table()
        elif event.button.id == "btn-sort-alpha":
            self._sort_by_time = False
            self._render_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._do_search()

    def _do_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            return
        self._set_status(f"Recherche en cours : {query!r} ...")
        self._search_satellite(query)

    def _set_status(self, msg: str) -> None:
        self._status_msg = msg
        self.query_one("#status-label", Label).update(msg)

    @work(thread=True)
    def _load_passes(self) -> None:
        self._set_status("Calcul des passages en cours...")
        from skyfield.api import load as sf_load
        from satrx.tracking.passes import find_passes
        from satrx.tracking.station import GroundStation
        from satrx.tracking.tle import fetch_tle_celestrak

        ts = sf_load.timescale()
        station = GroundStation(
            name=self._config.station_name,
            latitude_deg=self._config.latitude_deg,
            longitude_deg=self._config.longitude_deg,
            elevation_m=self._config.elevation_m,
        )
        now = datetime.now(timezone.utc)
        t_start = ts.from_datetime(now)
        t_end = ts.from_datetime(now + timedelta(hours=24))

        # On calcule les passages de tous les favoris + known satellites
        to_compute = list(self._favorites)
        known_ids = {f.norad_id for f in to_compute}
        for k in KNOWN_SATELLITES:
            if k.norad_id not in known_ids:
                to_compute.append(k)

        passes: list[PassInfo] = []
        fav_ids = {f.norad_id for f in self._favorites}

        for entry in to_compute:
            try:
                sat = fetch_tle_celestrak(entry.norad_id, timeout_s=8.0)
                sat_passes = find_passes(sat, station, t_start, t_end, min_elevation_deg=10.0)
                for sp in sat_passes[:3]:
                    aos_dt = sp.rise_time.utc_datetime()
                    los_dt = sp.set_time.utc_datetime()
                    passes.append(
                        PassInfo(
                            satellite_name=entry.name,
                            norad_id=entry.norad_id,
                            aos_utc=aos_dt,
                            los_utc=los_dt,
                            max_elevation_deg=sp.max_elevation_deg,
                            is_favorite=entry.norad_id in fav_ids,
                        )
                    )
            except Exception:
                continue

        self._passes = passes
        self.app.call_from_thread(self._render_table)
        self.app.call_from_thread(self._set_status, f"{len(passes)} passages trouves (24h)")

    @work(thread=True)
    def _search_satellite(self, query: str) -> None:
        from satrx.tracking.passes import find_passes
        from satrx.tracking.station import GroundStation
        from satrx.tracking.tle import fetch_tle_celestrak
        from skyfield.api import load as sf_load

        # Essai par NORAD ID d'abord, puis par nom dans KNOWN_SATELLITES
        norad_id: int | None = None
        name = query
        try:
            norad_id = int(query)
        except ValueError:
            for k in KNOWN_SATELLITES:
                if query.upper() in k.name.upper():
                    norad_id = k.norad_id
                    name = k.name
                    break

        if norad_id is None:
            self.app.call_from_thread(
                self._set_status,
                f"⚠ '{query}' introuvable - essayer avec le NORAD ID (ex: 57166)",
            )
            return

        try:
            ts = sf_load.timescale()
            station = GroundStation(
                name=self._config.station_name,
                latitude_deg=self._config.latitude_deg,
                longitude_deg=self._config.longitude_deg,
                elevation_m=self._config.elevation_m,
            )
            now = datetime.now(timezone.utc)
            sat = fetch_tle_celestrak(norad_id, timeout_s=8.0)
            name = sat.name or name
            t_start = ts.from_datetime(now)
            t_end = ts.from_datetime(now + timedelta(hours=48))
            sat_passes = find_passes(sat, station, t_start, t_end, min_elevation_deg=10.0)

            fav_ids = {f.norad_id for f in self._favorites}
            new_passes = [
                PassInfo(
                    satellite_name=name,
                    norad_id=norad_id,
                    aos_utc=sp.rise_time.utc_datetime(),
                    los_utc=sp.set_time.utc_datetime(),
                    max_elevation_deg=sp.max_elevation_deg,
                    is_favorite=norad_id in fav_ids,
                )
                for sp in sat_passes[:5]
            ]

            # Injecter dans la liste existante (remplace les anciennes entrees)
            existing = [p for p in self._passes if p.norad_id != norad_id]
            self._passes = existing + new_passes
            self.app.call_from_thread(self._render_table)
            self.app.call_from_thread(
                self._set_status,
                f"✓ {name} - {len(new_passes)} passages trouves (48h)",
            )
        except Exception as exc:
            self.app.call_from_thread(
                self._set_status, f"✖ Erreur pour {name} : {exc}"
            )

    def _render_table(self) -> None:
        table = self.query_one("#passes-table", DataTable)
        table.clear()

        if self._sort_by_time:
            sorted_passes = sorted(self._passes, key=lambda p: p.aos_utc)
            # Favoris en tete, puis reste par heure
            favs = [p for p in sorted_passes if p.is_favorite]
            others = [p for p in sorted_passes if not p.is_favorite]
            ordered = favs + others
        else:
            ordered = sorted(self._passes, key=lambda p: p.satellite_name.upper())

        for p in ordered:
            fav_mark = "[bold #FFD700]★[/]" if p.is_favorite else " "
            countdown = _format_countdown(p.seconds_until_aos)
            mm, ss = divmod(int(p.duration_s), 60)
            dur = f"{mm}m{ss:02d}s"
            elev_cell = f"{p.max_elevation_deg:.1f}° {p.elevation_symbol}"
            aos_str = p.aos_utc.strftime("%H:%M:%S")
            table.add_row(
                fav_mark,
                p.satellite_name,
                aos_str,
                countdown,
                dur,
                elev_cell,
                str(p.norad_id),
            )

    def action_toggle_favorite(self) -> None:
        table = self.query_one("#passes-table", DataTable)
        if table.cursor_row < 0 or table.cursor_row >= len(self._passes):
            return
        # Retrouver le passinfo correspondant a la ligne curseur
        if self._sort_by_time:
            sorted_passes = sorted(self._passes, key=lambda p: p.aos_utc)
            favs = [p for p in sorted_passes if p.is_favorite]
            others = [p for p in sorted_passes if not p.is_favorite]
            ordered = favs + others
        else:
            ordered = sorted(self._passes, key=lambda p: p.satellite_name.upper())

        if table.cursor_row >= len(ordered):
            return
        selected = ordered[table.cursor_row]

        fav_ids = {f.norad_id for f in self._favorites}
        if selected.norad_id in fav_ids:
            self._favorites = [f for f in self._favorites if f.norad_id != selected.norad_id]
        else:
            self._favorites.append(FavoriteEntry(selected.norad_id, selected.satellite_name))

        # Mettre a jour is_favorite dans la liste de passes
        updated: list[PassInfo] = []
        new_fav_ids = {f.norad_id for f in self._favorites}
        for p in self._passes:
            updated.append(
                PassInfo(
                    satellite_name=p.satellite_name,
                    norad_id=p.norad_id,
                    aos_utc=p.aos_utc,
                    los_utc=p.los_utc,
                    max_elevation_deg=p.max_elevation_deg,
                    is_favorite=p.norad_id in new_fav_ids,
                )
            )
        self._passes = updated

        if self._favorites_path is not None:
            save_favorites(self._favorites_path, self._favorites)

        self._render_table()

    def get_selected_pass(self) -> PassInfo | None:
        table = self.query_one("#passes-table", DataTable)
        if self._sort_by_time:
            sorted_passes = sorted(self._passes, key=lambda p: p.aos_utc)
            favs = [p for p in sorted_passes if p.is_favorite]
            others = [p for p in sorted_passes if not p.is_favorite]
            ordered = favs + others
        else:
            ordered = sorted(self._passes, key=lambda p: p.satellite_name.upper())
        if 0 <= table.cursor_row < len(ordered):
            return ordered[table.cursor_row]
        return None
