from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from satrx.acquisition.commands import (
    build_hackrf_transfer_command,
    build_recording_filename,
    build_rtl_sdr_command,
)
from satrx.acquisition.params import RecordingParams, SdrDevice

_EXTENSION_BY_DEVICE = {
    SdrDevice.RTL_SDR: "iq",
    SdrDevice.HACKRF: "cs8",
}


@dataclass(frozen=True)
class RecordingMetadata:
    params: RecordingParams
    device: SdrDevice
    start_time_utc: datetime
    output_file: str

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "satellite_name": self.params.satellite_name,
            "device": self.device.value,
            "center_freq_hz": self.params.center_freq_hz,
            "sample_rate_hz": self.params.sample_rate_hz,
            "duration_s": self.params.duration_s,
            "gain_db": self.params.gain_db,
            "ppm_correction": self.params.ppm_correction,
            "start_time_utc": self.start_time_utc.astimezone(timezone.utc).isoformat(),
            "output_file": self.output_file,
        }
        # Champs optionnels presents seulement si renseignes dans RecordingParams
        if self.params.satellite_freq_hz is not None:
            d["satellite_freq_hz"] = self.params.satellite_freq_hz
        if self.params.freq_offset_khz is not None:
            d["freq_offset_khz"] = self.params.freq_offset_khz
        return d


def write_metadata_sidecar(metadata: RecordingMetadata, path: Path) -> None:
    path.write_text(json.dumps(metadata.to_dict(), indent=2))


def record_iq(
    device: SdrDevice,
    params: RecordingParams,
    output_dir: Path,
    timeout_margin_s: float = 30.0,
) -> RecordingMetadata:
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(timezone.utc)
    extension = _EXTENSION_BY_DEVICE[device]
    filename = build_recording_filename(params, start_time, extension)
    output_path = output_dir / filename

    command = (
        build_rtl_sdr_command(params, output_path)
        if device is SdrDevice.RTL_SDR
        else build_hackrf_transfer_command(params, output_path)
    )
    subprocess.run(command, check=True, timeout=params.duration_s + timeout_margin_s)

    metadata = RecordingMetadata(
        params=params, device=device, start_time_utc=start_time, output_file=filename
    )
    write_metadata_sidecar(metadata, output_path.with_suffix(output_path.suffix + ".json"))
    return metadata


_HACKRF_STATS_RE = re.compile(
    r"([\d.]+)\s*MiB\s*/\s*([\d.]+)\s*sec\s*=\s*([\d.]+)\s*MiB/second,\s*average power\s*(-?[\d.]+)\s*dBfs"
)


@dataclass(frozen=True)
class RecordingStats:
    mib_transferred: float
    interval_s: float
    mib_per_second: float
    average_power_dbfs: float


def parse_hackrf_stats_line(line: str) -> RecordingStats | None:
    match = _HACKRF_STATS_RE.search(line)
    if match is None:
        return None
    mib, interval, rate, power = match.groups()
    return RecordingStats(
        mib_transferred=float(mib),
        interval_s=float(interval),
        mib_per_second=float(rate),
        average_power_dbfs=float(power),
    )


def start_recording_process(
    device: SdrDevice,
    params: RecordingParams,
    output_dir: Path,
) -> tuple[subprocess.Popen[str], RecordingMetadata, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(timezone.utc)
    extension = _EXTENSION_BY_DEVICE[device]
    filename = build_recording_filename(params, start_time, extension)
    output_path = output_dir / filename

    command = (
        build_rtl_sdr_command(params, output_path)
        if device is SdrDevice.RTL_SDR
        else build_hackrf_transfer_command(params, output_path)
    )

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    metadata = RecordingMetadata(
        params=params, device=device, start_time_utc=start_time, output_file=filename
    )
    return process, metadata, output_path
