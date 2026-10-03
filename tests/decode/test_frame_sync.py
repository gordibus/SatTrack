import pytest

from satrx.decode.frame_sync import (
    DEFAULT_CCSDS_ASM,
    METEOR_LRPT_CADU_LENGTH_BITS,
    bits_to_bytes,
    bytes_to_bits,
    extract_frames,
    find_sync_markers,
    hamming_distance_bits,
)


def _payload_bits(n_bytes: int, seed_byte: int = 0xA5) -> list[int]:
    return bytes_to_bits(bytes([(seed_byte + i) % 256 for i in range(n_bytes)]))


class TestMeteorLrptConstants:

    def test_cadu_length_matches_confirmed_ccsds_value(self):
        assert METEOR_LRPT_CADU_LENGTH_BITS == 8192
        assert METEOR_LRPT_CADU_LENGTH_BITS % 8 == 0

    def test_default_asm_matches_confirmed_meteor_value(self):
        assert DEFAULT_CCSDS_ASM == bytes.fromhex("1ACFFC1D")


class TestBitsBytesRoundtrip:

    def test_nominal_case(self):
        data = bytes([0x1A, 0xCF, 0xFC, 0x1D])

        bits = bytes_to_bits(data)
        back = bits_to_bytes(bits)

        assert len(bits) == 32
        assert back == data

    def test_edge_case_bit_count_not_multiple_of_8(self):
        with pytest.raises(ValueError):
            bits_to_bytes([0, 1, 1])


class TestHammingDistanceBits:

    def test_nominal_case(self):
        assert hamming_distance_bits([0, 1, 1, 0], [0, 1, 1, 0]) == 0
        assert hamming_distance_bits([0, 1, 1, 0], [1, 1, 1, 1]) == 2

    def test_edge_case_length_mismatch(self):
        with pytest.raises(ValueError):
            hamming_distance_bits([0, 1], [0, 1, 1])


class TestFindSyncMarkers:

    def test_nominal_case_exact_marker(self):
        bitstream = _payload_bits(4) + bytes_to_bits(DEFAULT_CCSDS_ASM) + _payload_bits(4)

        matches = find_sync_markers(bitstream, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)

        assert len(matches) == 1
        assert matches[0].bit_offset == 4 * 8
        assert matches[0].hamming_distance == 0

    def test_nominal_case_tolerates_bit_errors(self):
        marker_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)
        noisy_marker = list(marker_bits)
        noisy_marker[3] ^= 1
        bitstream = _payload_bits(2) + noisy_marker + _payload_bits(2)

        matches = find_sync_markers(bitstream, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=2)

        assert any(m.bit_offset == 2 * 8 and m.hamming_distance == 1 for m in matches)

    def test_edge_case_empty_bitstream(self):
        with pytest.raises(ValueError):
            find_sync_markers([], marker=DEFAULT_CCSDS_ASM)


class TestExtractFrames:

    def test_nominal_case_multiple_frames(self):
        frame_payload = bytes([0x11, 0x22, 0x33, 0x44])
        one_frame = DEFAULT_CCSDS_ASM + frame_payload
        bitstream = bytes_to_bits(one_frame + one_frame)

        frames = extract_frames(
            bitstream,
            frame_length_bits=len(one_frame) * 8,
            marker=DEFAULT_CCSDS_ASM,
            max_hamming_distance=0,
        )

        assert frames == [one_frame, one_frame]

    def test_edge_case_frame_length_not_multiple_of_8(self):
        with pytest.raises(ValueError):
            extract_frames([0, 1] * 100, frame_length_bits=13)

    def test_interop_with_find_sync_markers(self):
        frame_payload = bytes([0xAA, 0xBB])
        one_frame = DEFAULT_CCSDS_ASM + frame_payload
        bitstream = bytes_to_bits(one_frame)

        markers = find_sync_markers(bitstream, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)
        frames = extract_frames(
            bitstream, frame_length_bits=len(one_frame) * 8, marker=DEFAULT_CCSDS_ASM
        )

        assert markers[0].bit_offset == 0
        assert frames[0] == one_frame
