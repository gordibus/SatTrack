from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

from skyfield.api import EarthSatellite, load

CELESTRAK_TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE"


def parse_tle_text(text: str) -> tuple[str, str, str]:
    lines = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("TLE invalide : moins de deux lignes de donnees")

    if len(lines) >= 3:
        name, line1, line2 = lines[0].strip(), lines[1], lines[2]
    else:
        name, line1, line2 = "UNKNOWN", lines[0], lines[1]

    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError(
            "TLE invalide : la ligne 1 doit commencer par '1 ' et la ligne 2 par '2 '"
        )
    return name, line1, line2


def load_satellite(name: str, line1: str, line2: str) -> EarthSatellite:
    ts = load.timescale()
    return EarthSatellite(line1, line2, name, ts)


def load_satellite_from_file(path: Path) -> EarthSatellite:
    name, line1, line2 = parse_tle_text(path.read_text())
    return load_satellite(name, line1, line2)


def fetch_tle_celestrak(catalog_number: int, timeout_s: float = 10.0) -> EarthSatellite:
    if catalog_number <= 0:
        raise ValueError(f"catalog_number doit etre positif, recu {catalog_number}")

    url = CELESTRAK_TLE_URL.format(catnr=catalog_number)
    with urlopen(url, timeout=timeout_s) as response:
        text = response.read().decode("utf-8")

    name, line1, line2 = parse_tle_text(text)
    return load_satellite(name, line1, line2)
