import random

import pytest

from satrx.decode.reed_solomon import (
    DEFAULT_INTERLEAVE_DEPTH,
    DEFAULT_K,
    DEFAULT_NSYM,
    deinterleave_codewords,
    interleave_codewords,
    rs_decode,
    rs_decode_batch,
    rs_decode_interleaved,
    rs_encode,
    rs_encode_interleaved,
)


class TestRsEncode:

    def test_nominal_case_output_length(self):
        message = list(range(DEFAULT_K))

        encoded = rs_encode(message)

        assert len(encoded) == DEFAULT_K + DEFAULT_NSYM
        assert encoded[: DEFAULT_K] == message

    def test_edge_case_invalid_symbol_value(self):
        with pytest.raises(ValueError):
            rs_encode([0, 1, 256])

    def test_edge_case_invalid_nsym(self):
        with pytest.raises(ValueError):
            rs_encode([1, 2, 3], nsym=0)


class TestRsDecode:

    def test_nominal_case_no_errors_roundtrip(self):
        message = list(range(DEFAULT_K))

        encoded = rs_encode(message)
        decoded = rs_decode(encoded)

        assert decoded == message

    def test_nominal_case_corrects_scattered_errors(self):
        rng = random.Random(42)
        message = [rng.randint(0, 255) for _ in range(DEFAULT_K)]
        encoded = rs_encode(message)

        corrupted = list(encoded)
        max_correctable = DEFAULT_NSYM // 2
        error_positions = rng.sample(range(len(corrupted)), max_correctable)
        for pos in error_positions:
            corrupted[pos] = (corrupted[pos] + rng.randint(1, 255)) % 256

        decoded = rs_decode(corrupted)

        assert decoded == message

    def test_edge_case_too_many_errors_raises(self):
        rng = random.Random(7)
        message = [rng.randint(0, 255) for _ in range(DEFAULT_K)]
        encoded = rs_encode(message)

        corrupted = list(encoded)
        too_many = DEFAULT_NSYM // 2 + 1
        error_positions = rng.sample(range(len(corrupted)), too_many)
        for pos in error_positions:
            corrupted[pos] = (corrupted[pos] + rng.randint(1, 255)) % 256

        with pytest.raises(ValueError):
            rs_decode(corrupted)

    def test_edge_case_codeword_too_short(self):
        with pytest.raises(ValueError):
            rs_decode([1, 2, 3], nsym=32)

    def test_interop_encode_decode_with_alternate_nsym(self):
        message = [10, 200, 3, 250, 42, 99, 128, 7]

        encoded = rs_encode(message, nsym=4)
        corrupted = list(encoded)
        corrupted[1] ^= 0x7F
        corrupted[5] ^= 0x11

        decoded = rs_decode(corrupted, nsym=4)

        assert decoded == message


class TestRsDecodeBatch:

    def test_nominal_case_matches_rs_decode_no_errors(self):
        rng = random.Random(11)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(20)]
        codewords = [rs_encode(message) for message in messages]

        decoded = rs_decode_batch(codewords)

        assert decoded == messages

    def test_nominal_case_mixed_clean_and_corrupted_codewords(self):
        rng = random.Random(12)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(10)]
        codewords = [rs_encode(message) for message in messages]

        # corrompt seulement les mots de code d'indice pair, dans la limite correctible
        corrupted = [list(cw) for cw in codewords]
        for i in range(0, len(corrupted), 2):
            max_correctable = DEFAULT_NSYM // 2
            positions = rng.sample(range(len(corrupted[i])), max_correctable)
            for pos in positions:
                corrupted[i][pos] = (corrupted[i][pos] + rng.randint(1, 255)) % 256

        decoded = rs_decode_batch(corrupted)

        assert decoded == messages

    def test_edge_case_empty_codewords(self):
        with pytest.raises(ValueError):
            rs_decode_batch([])

    def test_edge_case_mismatched_lengths(self):
        with pytest.raises(ValueError):
            rs_decode_batch([[1] * 255, [1] * 200])

    def test_interop_matches_individual_rs_decode_calls(self):
        rng = random.Random(13)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(5)]
        codewords = [rs_encode(message) for message in messages]
        corrupted = [list(cw) for cw in codewords]
        corrupted[2][10] ^= 0xFF
        corrupted[2][20] ^= 0x01

        batch_result = rs_decode_batch(corrupted)
        individual_result = [rs_decode(cw) for cw in corrupted]

        assert batch_result == individual_result


class TestInterleaveDeinterleave:

    def test_nominal_case_roundtrip(self):
        codewords = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]

        interleaved = interleave_codewords(codewords)
        recovered = deinterleave_codewords(interleaved, depth=4)

        assert interleaved == [1, 4, 7, 10, 2, 5, 8, 11, 3, 6, 9, 12]
        assert recovered == codewords

    def test_edge_case_empty_codewords(self):
        with pytest.raises(ValueError):
            interleave_codewords([])

    def test_edge_case_mismatched_lengths(self):
        with pytest.raises(ValueError):
            interleave_codewords([[1, 2], [1, 2, 3]])

    def test_edge_case_deinterleave_not_multiple_of_depth(self):
        with pytest.raises(ValueError):
            deinterleave_codewords([1, 2, 3], depth=4)


class TestRsEncodeDecodeInterleaved:

    def test_nominal_case_default_depth(self):
        rng = random.Random(0)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(DEFAULT_INTERLEAVE_DEPTH)]

        data = rs_encode_interleaved(messages)

        assert len(data) == DEFAULT_INTERLEAVE_DEPTH * (DEFAULT_K + DEFAULT_NSYM)

        decoded = rs_decode_interleaved(data)

        assert decoded == messages

    def test_nominal_case_corrects_errors_spread_across_codewords(self):
        rng = random.Random(1)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(4)]
        data = rs_encode_interleaved(messages)

        corrupted = list(data)
        error_positions = rng.sample(range(len(corrupted)), 40)
        for pos in error_positions:
            corrupted[pos] = (corrupted[pos] + rng.randint(1, 255)) % 256

        decoded = rs_decode_interleaved(corrupted)

        assert decoded == messages

    def test_edge_case_empty_messages(self):
        with pytest.raises(ValueError):
            rs_encode_interleaved([])

    def test_interop_with_ccsds_cadu_length(self):
        # verifie que la taille d'un flux RS entrelace par defaut correspond bien
        # a la portion "donnees" d'un CADU Meteor-M (1024 octets = 8192 bits, ASM inclus)
        from satrx.decode.frame_sync import METEOR_LRPT_CADU_LENGTH_BITS

        rng = random.Random(2)
        messages = [[rng.randint(0, 255) for _ in range(DEFAULT_K)] for _ in range(DEFAULT_INTERLEAVE_DEPTH)]
        data = rs_encode_interleaved(messages)

        cadu_length_bytes = METEOR_LRPT_CADU_LENGTH_BITS // 8
        asm_bytes = 4
        assert len(data) == cadu_length_bytes - asm_bytes
