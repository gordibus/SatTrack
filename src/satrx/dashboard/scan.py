from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaptureRecord:
    metadata_path: Path
    iq_file: str
    satellite_name: str
    device: str
    center_freq_hz: float
    sample_rate_hz: float
    duration_s: float
    gain_db: float | None
    start_time_utc: str
    image_path: Path | None


def _find_matching_image(processed_dir: Path, iq_file: str) -> Path | None:
    stem = Path(iq_file).stem
    matches = sorted(processed_dir.glob(f"{stem}*.png"))
    return matches[0] if matches else None


# Sidecars ecrits par `acquisition/recorder.py::write_metadata_sidecar` (extension du
# fichier IQ + ".json", cf. `_EXTENSION_BY_DEVICE`). Ne pas utiliser un motif "*.json" trop
# large : `data/raw/` contient aussi les plans de capture du TUI (`.capture_plan_*.json`,
# schema different) qui doivent etre ignores plutot que provoquer une erreur de cle absente.
_METADATA_SIDECAR_GLOBS = ("*.cs8.json", "*.iq.json")


def scan_recordings(raw_dir: Path, processed_dir: Path | None = None) -> list[CaptureRecord]:
    if not raw_dir.is_dir():
        raise ValueError(f"raw_dir n'est pas un dossier existant : {raw_dir}")

    metadata_paths = sorted(
        {path for pattern in _METADATA_SIDECAR_GLOBS for path in raw_dir.glob(pattern)}
    )

    records: list[CaptureRecord] = []
    for metadata_path in metadata_paths:
        data = json.loads(metadata_path.read_text())

        image_path = None
        if processed_dir is not None and processed_dir.is_dir():
            image_path = _find_matching_image(processed_dir, str(data["output_file"]))

        gain_db = data.get("gain_db")
        records.append(
            CaptureRecord(
                metadata_path=metadata_path,
                iq_file=str(data["output_file"]),
                satellite_name=str(data["satellite_name"]),
                device=str(data["device"]),
                center_freq_hz=float(data["center_freq_hz"]),
                sample_rate_hz=float(data["sample_rate_hz"]),
                duration_s=float(data["duration_s"]),
                gain_db=(float(gain_db) if gain_db is not None else None),
                start_time_utc=str(data["start_time_utc"]),
                image_path=image_path,
            )
        )
    return records
