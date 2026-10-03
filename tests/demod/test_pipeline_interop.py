import numpy as np

from satrx.decode.frame_sync import DEFAULT_CCSDS_ASM, bytes_to_bits, find_sync_markers
from satrx.demod.qpsk import downsample_to_symbol_rate, slice_qpsk_symbols


def _dibit_to_qpsk_symbol(bit_i: int, bit_q: int) -> complex:
    return complex(-1.0 if bit_i else 1.0, -1.0 if bit_q else 1.0)


class TestDemodToFrameSyncPipeline:

    def test_iq_samples_to_recovered_sync_marker(self):
        payload_bits = [1, 0, 1, 1, 0, 0, 1, 0]
        asm_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)
        bits = payload_bits + asm_bits + payload_bits

        symbols = [
            _dibit_to_qpsk_symbol(bits[i], bits[i + 1]) for i in range(0, len(bits), 2)
        ]
        sps = 4
        iq_samples = np.repeat(np.array(symbols, dtype=np.complex128), sps)

        downsampled = downsample_to_symbol_rate(iq_samples, samples_per_symbol=sps)
        recovered_bits = slice_qpsk_symbols(downsampled).tolist()

        assert recovered_bits == bits

        matches = find_sync_markers(recovered_bits, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)

        assert any(m.bit_offset == len(payload_bits) for m in matches)
