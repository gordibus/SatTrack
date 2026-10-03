#!/usr/bin/env python3
"""Genere un tableau de bord HTML statique (F11) a partir des captures IQ
enregistrees (data/raw/*.json) et des images decodees correspondantes
(data/processed/*.png).

Usage:
    poetry run python scripts/generate_dashboard.py
    poetry run python scripts/generate_dashboard.py --raw-dir data/raw \
        --processed-dir data/processed --output data/processed/dashboard.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from satrx.dashboard import scan_recordings, write_report  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw")
    parser.add_argument("--processed-dir", type=Path, default=PROJECT_ROOT / "data" / "processed")
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "data" / "processed" / "dashboard.html"
    )
    args = parser.parse_args()

    records = scan_recordings(args.raw_dir, args.processed_dir)
    write_report(records, args.output)
    print(f"{len(records)} capture(s) recensee(s) -> {args.output}")


if __name__ == "__main__":
    main()
