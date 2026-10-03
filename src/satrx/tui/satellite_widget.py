from __future__ import annotations

import random

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from satrx.tracking.passes import TrajectoryPoint

_ROWS = 9
_SAT_MARKER = "\U0001f6f0"  # satellite emoji - largeur 2 colonnes dans la plupart des terminaux
_TRAIL_MARKER = "·"


class SatelliteSkyWidget(Widget):
    DEFAULT_CSS = """
    SatelliteSkyWidget {
        height: 13;
        border: round $primary;
        background: #05050a;
    }
    """

    elapsed_s: reactive[float] = reactive(0.0)
    active: reactive[bool] = reactive(False)

    def __init__(self, trajectory: list[TrajectoryPoint], id: str | None = None) -> None:
        super().__init__(id=id)
        self._trajectory = trajectory
        self._total_s = trajectory[-1].seconds_from_start if trajectory else 1.0
        self._max_elevation = max((p.elevation_deg for p in trajectory), default=1.0)
        self._max_elevation = max(self._max_elevation, 1.0)
        self._stars: list[tuple[int, int, str]] = []
        self._stars_width: int = -1

    def _position_at(self, elapsed_s: float, width: int) -> tuple[int, int, float]:
        if not self._trajectory:
            return _ROWS - 2, 0, 0.0
        closest = min(self._trajectory, key=lambda p: abs(p.seconds_from_start - elapsed_s))
        col = int((closest.seconds_from_start / max(self._total_s, 1.0)) * (width - 1))
        col = max(0, min(width - 1, col))
        elevation = max(closest.elevation_deg, 0.0)
        row = (_ROWS - 2) - int((elevation / self._max_elevation) * (_ROWS - 3))
        row = max(0, min(_ROWS - 2, row))
        return row, col, closest.elevation_deg

    def render(self) -> Text:
        width = max(self.size.width - 2, 20)

        if len(self._stars) == 0 or self._stars_width != width:
            rng = random.Random(1337)
            self._stars = [
                (rng.randrange(_ROWS - 1), rng.randrange(width), rng.choice("·.:"))
                for _ in range(int(width * (_ROWS - 1) * 0.04))
            ]
            self._stars_width = width

        grid = [[" " for _ in range(width)] for _ in range(_ROWS)]
        for r, c, ch in self._stars:
            if r < _ROWS - 1 and c < width:
                grid[r][c] = ch

        for c in range(width):
            grid[_ROWS - 1][c] = "─"

        row, col, elevation = self._position_at(self.elapsed_s, width)

        for point in self._trajectory:
            if point.seconds_from_start > self.elapsed_s:
                break
            pr, pc, _ = self._position_at(point.seconds_from_start, width)
            if grid[pr][pc] == " ":
                grid[pr][pc] = _TRAIL_MARKER

        grid[row][col] = _SAT_MARKER
        if col + 1 < width:
            grid[row][col + 1] = ""  # l'emoji occupe 2 colonnes terminal, on reserve la suivante

        text = Text()
        marker_style = "bold #ff00d4" if self.active else "bold #00fff2"
        for r in range(_ROWS):
            for c in range(width):
                ch = grid[r][c]
                if ch == "":
                    continue
                if r == _ROWS - 1:
                    text.append(ch, style="#1a6b66")
                elif ch == _SAT_MARKER:
                    text.append(ch, style=marker_style)
                elif ch == _TRAIL_MARKER:
                    text.append(ch, style="#ff00d4" if self.active else "#0a4f4a")
                elif ch != " ":
                    text.append(ch, style="#0d3b38")
                else:
                    text.append(ch)
            text.append("\n")

        elev_label = f" elevation actuelle : {elevation:5.1f} deg "
        text.append(elev_label, style="bold #00fff2 on #05050a")
        return text

    def watch_elapsed_s(self, _value: float) -> None:
        self.refresh()
