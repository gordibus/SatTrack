from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from satrx.decode.frame_sync import DEFAULT_CCSDS_ASM, find_sync_markers
from satrx.demod.qpsk import slice_qpsk_symbols

ComplexSamples = NDArray[np.complex128]

# Un recepteur QPSK ne peut pas distinguer, par construction, 4 rotations de phase
# equivalentes (0/90/180/270 deg) - la boucle de Costas converge vers l'une d'elles
# arbitrairement. La resolution standard consiste a essayer les 4 et a chercher l'ASM.
QPSK_AMBIGUOUS_ROTATIONS_DEG = (0, 90, 180, 270)


def estimate_frequency_offset_4th_power(iq_samples: ComplexSamples, sample_rate_hz: float) -> float:
    if iq_samples.size == 0:
        raise ValueError("iq_samples ne doit pas etre vide")
    if sample_rate_hz <= 0.0:
        raise ValueError(f"sample_rate_hz doit etre positif, recu {sample_rate_hz}")

    fourth_power = iq_samples.astype(np.complex128) ** 4
    spectrum = np.fft.fftshift(np.fft.fft(fourth_power))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(iq_samples), d=1.0 / sample_rate_hz))
    peak_idx = int(np.argmax(np.abs(spectrum)))
    return float(freqs[peak_idx]) / 4.0


@dataclass(frozen=True)
class CostasLoopResult:
    corrected_symbols: ComplexSamples
    phase_history: NDArray[np.float64]
    frequency_history: NDArray[np.float64]


def costas_loop_qpsk(
    symbols: ComplexSamples,
    loop_bandwidth: float = 0.02,
    damping_factor: float = 0.707,
) -> CostasLoopResult:
    if symbols.size == 0:
        raise ValueError("symbols ne doit pas etre vide")
    if loop_bandwidth <= 0.0:
        raise ValueError(f"loop_bandwidth doit etre positif, recu {loop_bandwidth}")
    if damping_factor <= 0.0:
        raise ValueError(f"damping_factor doit etre positif, recu {damping_factor}")

    theta = loop_bandwidth
    denom = 1.0 + 2.0 * damping_factor * theta + theta * theta
    alpha = (4.0 * damping_factor * theta) / denom
    beta = (4.0 * theta * theta) / denom

    n = symbols.size
    corrected = np.zeros(n, dtype=np.complex128)
    phase_history = np.zeros(n, dtype=np.float64)
    frequency_history = np.zeros(n, dtype=np.float64)

    phase = 0.0
    freq = 0.0
    for i in range(n):
        rotated = symbols[i] * np.exp(-1j * phase)
        corrected[i] = rotated

        decision_real = 1.0 if rotated.real >= 0.0 else -1.0
        decision_imag = 1.0 if rotated.imag >= 0.0 else -1.0
        error = decision_real * rotated.imag - decision_imag * rotated.real

        freq += beta * error
        phase += freq + alpha * error
        phase = float(np.mod(phase + np.pi, 2.0 * np.pi) - np.pi)

        phase_history[i] = phase
        frequency_history[i] = freq

    return CostasLoopResult(
        corrected_symbols=corrected, phase_history=phase_history, frequency_history=frequency_history
    )


@dataclass(frozen=True)
class AmbiguityResolution:
    bits: list[int]
    rotation_deg: int
    bit_offset: int
    hamming_distance: int


def resolve_qpsk_phase_ambiguity(
    symbols: ComplexSamples,
    marker: bytes = DEFAULT_CCSDS_ASM,
    max_hamming_distance: int = 4,
) -> AmbiguityResolution | None:
    if symbols.size == 0:
        raise ValueError("symbols ne doit pas etre vide")

    for rotation_deg in QPSK_AMBIGUOUS_ROTATIONS_DEG:
        rotated = symbols * np.exp(1j * np.deg2rad(rotation_deg))
        bits = slice_qpsk_symbols(rotated).tolist()
        matches = find_sync_markers(bits, marker=marker, max_hamming_distance=max_hamming_distance)
        if matches:
            best = min(matches, key=lambda m: m.hamming_distance)
            return AmbiguityResolution(
                bits=bits,
                rotation_deg=rotation_deg,
                bit_offset=best.bit_offset,
                hamming_distance=best.hamming_distance,
            )
    return None
