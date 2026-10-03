import numpy as np
import pytest

from satrx.demod.qpsk import (
    downsample_oqpsk_symbols,
    downsample_to_symbol_rate,
    slice_qpsk_symbols,
)


def _dibit_to_qpsk_symbol(bit_i: int, bit_q: int) -> complex:
    return complex(-1.0 if bit_i else 1.0, -1.0 if bit_q else 1.0)


def _bits_to_symbols(bits: list[int]) -> list[complex]:
    return [_dibit_to_qpsk_symbol(bits[i], bits[i + 1]) for i in range(0, len(bits), 2)]


class TestDownsampleToSymbolRate:

    def test_nominal_case_recovers_symbols_from_rectangular_pulses(self):
        bits = [1, 0, 0, 1, 1, 1, 0, 0]
        symbols = np.array(_bits_to_symbols(bits), dtype=np.complex128)
        sps = 4
        iq_samples = np.repeat(symbols, sps)

        recovered = downsample_to_symbol_rate(iq_samples, samples_per_symbol=sps)

        assert np.array_equal(recovered, symbols)

    def test_edge_case_invalid_samples_per_symbol(self):
        with pytest.raises(ValueError):
            downsample_to_symbol_rate(np.array([1 + 1j]), samples_per_symbol=0)

    def test_edge_case_offset_out_of_range(self):
        with pytest.raises(ValueError):
            downsample_to_symbol_rate(np.zeros(8, dtype=np.complex128), samples_per_symbol=4, symbol_offset=4)


class TestSliceQpskSymbols:

    def test_nominal_case_roundtrip(self):
        bits = [1, 0, 0, 1, 1, 1, 0, 0]
        symbols = np.array(_bits_to_symbols(bits), dtype=np.complex128)

        recovered_bits = slice_qpsk_symbols(symbols)

        assert recovered_bits.tolist() == bits

    def test_edge_case_empty_symbols(self):
        with pytest.raises(ValueError):
            slice_qpsk_symbols(np.array([], dtype=np.complex128))

    def test_nominal_case_robust_to_small_noise(self):
        bits = [1, 0, 0, 1, 1, 1, 0, 0, 0, 0]
        symbols = np.array(_bits_to_symbols(bits), dtype=np.complex128)
        rng = np.random.default_rng(42)
        noise = (rng.normal(scale=0.2, size=symbols.shape) + 1j * rng.normal(scale=0.2, size=symbols.shape))
        noisy_symbols = symbols + noise

        recovered_bits = slice_qpsk_symbols(noisy_symbols)

        assert recovered_bits.tolist() == bits

    def test_interop_downsample_then_slice_recovers_original_bits(self):
        bits = [0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1]
        symbols = np.array(_bits_to_symbols(bits), dtype=np.complex128)
        sps = 8
        iq_samples = np.repeat(symbols, sps)

        downsampled = downsample_to_symbol_rate(iq_samples, samples_per_symbol=sps)
        recovered_bits = slice_qpsk_symbols(downsampled)

        assert recovered_bits.tolist() == bits


class TestDownsampleOqpskSymbols:

    def test_nominal_case_recovers_symbols_with_half_symbol_q_delay(self):
        bits = [1, 0, 0, 1, 1, 1, 0, 0]
        symbols = _bits_to_symbols(bits)
        i_vals = [s.real for s in symbols]
        q_vals = [s.imag for s in symbols]
        sps = 4
        half = sps // 2

        i_full = np.repeat(i_vals, sps)
        q_full_unshifted = np.repeat(q_vals, sps)
        q_full = np.concatenate([np.full(half, q_vals[0]), q_full_unshifted])[: len(i_full)]
        iq_samples = (i_full + 1j * q_full).astype(np.complex128)

        recovered = downsample_oqpsk_symbols(iq_samples, samples_per_symbol=sps)

        assert np.allclose(recovered, symbols)

    def test_edge_case_odd_samples_per_symbol(self):
        with pytest.raises(ValueError):
            downsample_oqpsk_symbols(np.zeros(9, dtype=np.complex128), samples_per_symbol=3)

    def test_interop_with_slice_qpsk_symbols(self):
        bits = [1, 1, 0, 0, 1, 0, 0, 1]
        symbols = _bits_to_symbols(bits)
        i_vals = [s.real for s in symbols]
        q_vals = [s.imag for s in symbols]
        sps = 6
        half = sps // 2

        i_full = np.repeat(i_vals, sps)
        q_full_unshifted = np.repeat(q_vals, sps)
        q_full = np.concatenate([np.full(half, q_vals[0]), q_full_unshifted])[: len(i_full)]
        iq_samples = (i_full + 1j * q_full).astype(np.complex128)

        recovered_symbols = downsample_oqpsk_symbols(iq_samples, samples_per_symbol=sps)
        recovered_bits = slice_qpsk_symbols(recovered_symbols)

        assert recovered_bits.tolist() == bits
