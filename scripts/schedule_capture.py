#!/usr/bin/env python3
"""Programme une capture IQ a une heure donnee et ouvre un nouveau terminal
avec une visualisation TUI en direct (satrx.tui.app) pendant l'attente et
l'enregistrement. L'appel a ce script revient immediatement : le suivi et
l'enregistrement se poursuivent dans le nouveau terminal.

Usage:
    poetry run python scripts/schedule_capture.py \
        --satellite "METEOR-M2 3" --tle-file data/raw/meteor_m_tle.txt \
        --freq-mhz 137.9 --sample-rate-msps 2.048 --duration-s 660 \
        --start-at 21:28:24 --lat 48.910178 --lon 2.254915 \
        --lna-gain-db 32
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skyfield.api import load  # noqa: E402

from satrx.tracking.passes import compute_trajectory  # noqa: E402
from satrx.tracking.station import GroundStation  # noqa: E402
from satrx.tracking.tle import parse_tle_text  # noqa: E402
from satrx.tracking.tle import load_satellite as load_satellite_from_lines  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_satellite_by_name(tle_file: Path, name: str):
    lines = [line for line in tle_file.read_text().splitlines() if line.strip()]
    for i in range(0, len(lines) - 2, 3):
        block_name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if block_name.strip() == name.strip():
            _, l1, l2 = parse_tle_text(f"{block_name}\n{l1}\n{l2}\n")
            return load_satellite_from_lines(block_name.strip(), l1, l2)
    raise ValueError(f"satellite '{name}' introuvable dans {tle_file}")


def _parse_start_at(value: str) -> datetime:
    now_local = datetime.now().astimezone()
    if "T" in value or " " in value and len(value) > 10:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt.astimezone(timezone.utc)

    hh, mm, ss = (int(part) for part in value.split(":"))
    candidate = now_local.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    if candidate < now_local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--satellite", required=True)
    parser.add_argument("--tle-file", required=True, type=Path)
    parser.add_argument("--freq-mhz", required=True, type=float)
    parser.add_argument("--sample-rate-msps", default=2.048, type=float)
    parser.add_argument("--duration-s", required=True, type=float)
    parser.add_argument("--start-at", required=True, help="HH:MM:SS (aujourd'hui) ou ISO complet")
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--elevation-m", default=100.0, type=float)
    parser.add_argument(
        "--lna-gain-db", default=32.0, type=float,
        help="gain LNA/IF HackRF, 0-40dB par pas de 8 (defaut 32)",
    )
    parser.add_argument(
        "--gain-db", default=30.0, type=float,
        help="gain VGA/baseband HackRF, 0-62dB par pas de 2 (defaut 30 ; a 0/None hackrf_transfer "
        "ne fixe pas ce gain explicitement, ce qui a probablement nui a la reception du 16/08)",
    )
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--device", default="hackrf_transfer", choices=["hackrf_transfer", "rtl_sdr"])
    parser.add_argument("--output-dir", default=PROJECT_ROOT / "data" / "raw", type=Path)
    args = parser.parse_args()

    start_at_utc = _parse_start_at(args.start_at)
    station = GroundStation(name="station", latitude_deg=args.lat, longitude_deg=args.lon, elevation_m=args.elevation_m)
    satellite = _load_satellite_by_name(args.tle_file, args.satellite)

    ts = load.timescale()
    start_time = ts.from_datetime(start_at_utc)
    trajectory = compute_trajectory(satellite, station, start_time, args.duration_s, n_samples=200)

    plan = {
        "satellite_name": args.satellite,
        "device": args.device,
        "center_freq_hz": args.freq_mhz * 1e6,
        "sample_rate_hz": args.sample_rate_msps * 1e6,
        "duration_s": args.duration_s,
        "lna_gain_db": args.lna_gain_db,
        "gain_db": args.gain_db,
        "amplifier_enabled": args.amp,
        "start_at_utc": start_at_utc.isoformat(),
        "output_dir": str(args.output_dir),
        "trajectory": [
            {"seconds_from_start": p.seconds_from_start, "elevation_deg": p.elevation_deg, "azimuth_deg": p.azimuth_deg}
            for p in trajectory
        ],
    }

    plan_path = args.output_dir / f".capture_plan_{start_at_utc.strftime('%Y%m%dT%H%M%SZ')}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2))

    if shutil.which("gnome-terminal"):
        terminal_cmd = [
            "gnome-terminal",
            "--working-directory", str(PROJECT_ROOT),
            "--",
            "poetry", "run", "python", "-m", "satrx.tui.app", str(plan_path),
        ]
    elif shutil.which("x-terminal-emulator"):
        terminal_cmd = [
            "x-terminal-emulator", "-e",
            f"bash -c 'cd {PROJECT_ROOT} && poetry run python -m satrx.tui.app {plan_path}; exec bash'",
        ]
    else:
        print("Aucun emulateur de terminal trouve. Lancement direct ici :")
        subprocess.run(["poetry", "run", "python", "-m", "satrx.tui.app", str(plan_path)], cwd=PROJECT_ROOT)
        return

    subprocess.Popen(terminal_cmd, cwd=PROJECT_ROOT)
    local_start = start_at_utc.astimezone()
    print(f"Capture programmee pour {local_start.strftime('%H:%M:%S')} - TUI lance dans un nouveau terminal.")
    print(f"Plan : {plan_path}")


if __name__ == "__main__":
    main()
