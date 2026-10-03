import numpy as np
import pytest

from satrx.demod.qpsk import slice_qpsk_symbols
from satrx.demod.timing_recovery import estimate_symbol_timing_offset, extract_symbols_at_offset

_SPS = 8


def _rrc_filter(sps: int, span_symbols: int, rolloff: float) -> np.ndarray:
    n = span_symbols * sps
    t = np.arange(-n, n + 1) / sps
    h = np.zeros_like(t)
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = 1 - rolloff + 4 * rolloff / np.pi
        elif rolloff != 0 and abs(abs(4 * rolloff * ti) - 1) < 1e-8:
            h[i] = (rolloff / np.sqrt(2)) * (
                (1 + 2 / np.pi) * np.sin(np.pi / (4 * rolloff))
                + (1 - 2 / np.pi) * np.cos(np.pi / (4 * rolloff))
            )
        else:
            h[i] = (np.sin(np.pi * ti * (1 - rolloff)) + 4 * rolloff * ti * np.cos(np.pi * ti * (1 + rolloff))) / (
                np.pi * ti * (1 - (4 * rolloff * ti) ** 2)
            )
    return h / np.sqrt(np.sum(h**2))


def _make_shaped_signal(bits: list[int], sps: int, frac_offset: float, noise_scale: float, seed: int):
    i_vals = np.where(np.array(bits[0::2]) == 0, 1.0, -1.0)
    q_vals = np.where(np.array(bits[1::2]) == 0, 1.0, -1.0)
    symbols = i_vals + 1j * q_vals

    zero_stuffed = np.zeros(len(symbols) * sps, dtype=complex)
    zero_stuffed[::sps] = symbols
    h = _rrc_filter(sps, 6, 0.35)
    shaped = np.convolve(zero_stuffed, h, mode="same")

    idx = np.arange(len(shaped)) - frac_offset
    idx_floor = np.clip(np.floor(idx).astype(int), 0, len(shaped) - 2)
    frac = idx - idx_floor
    delayed = (1 - frac) * shaped[idx_floor] + frac * shaped[idx_floor + 1]

    rng = np.random.default_rng(seed)
    noise = rng.normal(scale=noise_scale, size=len(delayed)) + 1j * rng.normal(scale=noise_scale, size=len(delayed))
    return (delayed + noise).astype(np.complex128)


class TestEstimateSymbolTimingOffset:

    def test_nominal_case_recovers_bits_despite_unknown_fractional_delay(self):
        rng = np.random.default_rng(1)
        bits = rng.integers(0, 2, size=4000).tolist()
        received = _make_shaped_signal(bits, _SPS, frac_offset=3.4, noise_scale=0.05, seed=2)

        offset = estimate_symbol_timing_offset(received, _SPS)
        symbols = extract_symbols_at_offset(received, _SPS, offset)
        recovered_bits = slice_qpsk_symbols(symbols).tolist()

        n = min(len(recovered_bits), len(bits))
        assert recovered_bits[:n] == bits[:n]

    def test_nominal_case_different_offset(self):
        rng = np.random.default_rng(3)
        bits = rng.integers(0, 2, size=3000).tolist()
        received = _make_shaped_signal(bits, _SPS, frac_offset=5.9, noise_scale=0.08, seed=4)

        offset = estimate_symbol_timing_offset(received, _SPS)
        symbols = extract_symbols_at_offset(received, _SPS, offset)
        recovered_bits = slice_qpsk_symbols(symbols).tolist()

        n = min(len(recovered_bits), len(bits))
        assert recovered_bits[:n] == bits[:n]

    def test_edge_case_empty_samples(self):
        with pytest.raises(ValueError):
            estimate_symbol_timing_offset(np.array([], dtype=np.complex128), _SPS)

    def test_edge_case_invalid_samples_per_symbol(self):
        with pytest.raises(ValueError):
            estimate_symbol_timing_offset(np.zeros(100, dtype=np.complex128), samples_per_symbol=1)

    def test_edge_case_too_short_for_reliable_estimate(self):
        with pytest.raises(ValueError):
            estimate_symbol_timing_offset(np.zeros(10, dtype=np.complex128), samples_per_symbol=8)


class TestExtractSymbolsAtOffset:

    def test_edge_case_empty_samples(self):
        with pytest.raises(ValueError):
            extract_symbols_at_offset(np.array([], dtype=np.complex128), _SPS, 0.0)

    def test_edge_case_offset_out_of_range(self):
        with pytest.raises(ValueError):
            extract_symbols_at_offset(np.zeros(100, dtype=np.complex128), _SPS, offset=_SPS)

    def test_interop_with_estimate_symbol_timing_offset(self):
        rng = np.random.default_rng(5)
        bits = rng.integers(0, 2, size=2000).tolist()
        received = _make_shaped_signal(bits, _SPS, frac_offset=1.1, noise_scale=0.05, seed=6)

        offset = estimate_symbol_timing_offset(received, _SPS)
        symbols = extract_symbols_at_offset(received, _SPS, offset)

        assert symbols.size > 0
        assert np.mean(np.abs(symbols)) > 0.3  # signal correctement centre, pas juste du bruit
