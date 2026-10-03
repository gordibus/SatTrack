import numpy as np
import pytest

from satrx.decode.frame_sync import DEFAULT_CCSDS_ASM, bytes_to_bits
from satrx.demod.costas import (
    costas_loop_qpsk,
    estimate_frequency_offset_4th_power,
    resolve_qpsk_phase_ambiguity,
)


def _bits_to_qpsk_symbols(bits: list[int]) -> np.ndarray:
    i_vals = np.array([1.0 if b == 0 else -1.0 for b in bits[0::2]])
    q_vals = np.array([1.0 if b == 0 else -1.0 for b in bits[1::2]])
    return (i_vals + 1j * q_vals).astype(np.complex128)


class TestEstimateFrequencyOffset4thPower:

    def test_nominal_case_recovers_known_offset(self):
        rng = np.random.default_rng(0)
        bits = rng.integers(0, 2, size=4000).tolist()
        symbols = _bits_to_qpsk_symbols(bits)
        true_offset = 0.0037
        t = np.arange(len(symbols))
        drifted = symbols * np.exp(1j * 2 * np.pi * true_offset * t)

        estimated = estimate_frequency_offset_4th_power(drifted, sample_rate_hz=1.0)

        assert estimated == pytest.approx(true_offset, abs=1e-4)

    def test_edge_case_empty_input(self):
        with pytest.raises(ValueError):
            estimate_frequency_offset_4th_power(np.array([], dtype=np.complex128), sample_rate_hz=1.0)

    def test_edge_case_invalid_sample_rate(self):
        with pytest.raises(ValueError):
            estimate_frequency_offset_4th_power(np.array([1 + 1j]), sample_rate_hz=0.0)


class TestCostasLoopQpsk:

    def test_nominal_case_converges_frequency_close_to_true(self):
        rng = np.random.default_rng(0)
        bits = rng.integers(0, 2, size=8000).tolist()
        symbols = _bits_to_qpsk_symbols(bits)
        true_offset = 0.003
        t = np.arange(len(symbols))
        drifted = symbols * np.exp(1j * (2 * np.pi * true_offset * t + 1.7))

        result = costas_loop_qpsk(drifted, loop_bandwidth=0.05)

        assert result.frequency_history[-1] == pytest.approx(2 * np.pi * true_offset, abs=0.01)

    def test_edge_case_empty_input(self):
        with pytest.raises(ValueError):
            costas_loop_qpsk(np.array([], dtype=np.complex128))

    def test_edge_case_invalid_loop_bandwidth(self):
        with pytest.raises(ValueError):
            costas_loop_qpsk(np.array([1 + 1j]), loop_bandwidth=0.0)

    def test_edge_case_invalid_damping_factor(self):
        with pytest.raises(ValueError):
            costas_loop_qpsk(np.array([1 + 1j]), damping_factor=-1.0)


class TestResolveQpskPhaseAmbiguity:

    def test_nominal_case_recovers_exact_payload_despite_unknown_rotation(self):
        rng = np.random.default_rng(1)
        asm_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)
        payload_bits = rng.integers(0, 2, size=2000).tolist()
        all_bits = asm_bits + payload_bits
        symbols = _bits_to_qpsk_symbols(all_bits)

        true_offset = -0.0021
        t = np.arange(len(symbols))
        drifted = symbols * np.exp(1j * (2 * np.pi * true_offset * t + 4.6))
        noise = rng.normal(scale=0.1, size=len(symbols)) + 1j * rng.normal(scale=0.1, size=len(symbols))
        received = drifted + noise

        estimated = estimate_frequency_offset_4th_power(received, sample_rate_hz=1.0)
        coarse_corrected = received * np.exp(-1j * 2 * np.pi * estimated * t)
        result = costas_loop_qpsk(coarse_corrected, loop_bandwidth=0.05)
        resolution = resolve_qpsk_phase_ambiguity(result.corrected_symbols)

        assert resolution is not None
        recovered_payload = resolution.bits[
            resolution.bit_offset + len(asm_bits) : resolution.bit_offset + len(asm_bits) + len(payload_bits)
        ]
        assert recovered_payload == payload_bits

    def test_edge_case_empty_symbols(self):
        with pytest.raises(ValueError):
            resolve_qpsk_phase_ambiguity(np.array([], dtype=np.complex128))

    def test_edge_case_no_asm_in_pure_noise_returns_none(self):
        rng = np.random.default_rng(2)
        noise_symbols = (
            rng.normal(scale=1.0, size=500) + 1j * rng.normal(scale=1.0, size=500)
        ).astype(np.complex128)

        resolution = resolve_qpsk_phase_ambiguity(noise_symbols, max_hamming_distance=0)

        assert resolution is None
