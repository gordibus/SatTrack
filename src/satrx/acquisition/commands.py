from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from satrx.acquisition.params import RecordingParams


def build_recording_filename(params: RecordingParams, start_time: datetime, extension: str) -> str:
    if start_time.tzinfo is None:
        raise ValueError("start_time doit etre timezone-aware (UTC recommande)")

    timestamp = start_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = "-".join(params.satellite_name.strip().split())
    freq_mhz = params.center_freq_hz / 1.0e6
    return f"{timestamp}_{safe_name}_{freq_mhz:.3f}MHz.{extension}"


def build_rtl_sdr_command(params: RecordingParams, output_path: Path) -> list[str]:
    n_samples = int(params.duration_s * params.sample_rate_hz)
    command = [
        "rtl_sdr",
        "-f",
        str(int(params.center_freq_hz)),
        "-s",
        str(int(params.sample_rate_hz)),
        "-n",
        str(n_samples),
    ]
    if params.gain_db is not None:
        command += ["-g", f"{params.gain_db:.1f}"]
    command.append(str(output_path))
    return command


def build_hackrf_transfer_command(params: RecordingParams, output_path: Path) -> list[str]:
    n_samples = int(params.duration_s * params.sample_rate_hz)
    # Appliquer la correction PPM sur la frequence commandee.
    # Si PPM > 0 (oscillateur trop haut), on commande une freq legerement plus basse
    # pour que l'OL reel soit a center_freq_hz.
    tuned_freq = int(round(params.center_freq_hz_ppm_corrected))
    command = [
        "hackrf_transfer",
        "-r",
        str(output_path),
        "-f",
        str(tuned_freq),
        "-s",
        str(int(params.sample_rate_hz)),
        "-n",
        str(n_samples),
    ]
    if params.gain_db is not None:
        command += ["-g", str(int(params.gain_db))]
    if params.lna_gain_db is not None:
        command += ["-l", str(int(params.lna_gain_db))]
    if params.amplifier_enabled:
        command += ["-a", "1"]
    return command
