import random

import pytest

from satrx.decode.jpeg_entropy import (
    EOB,
    STANDARD_AC_LUMINANCE_BITS,
    STANDARD_AC_LUMINANCE_VALUES,
    STANDARD_DC_LUMINANCE_BITS,
    STANDARD_DC_LUMINANCE_VALUES,
    ZRL,
    BitReader,
    BitWriter,
    build_huffman_decode_table,
    build_huffman_encode_table,
    decode_block,
    decode_huffman_symbol,
    encode_block,
    encode_huffman_symbol,
    receive_extend,
    standard_ac_luminance_decode_table,
    standard_ac_luminance_encode_table,
    standard_dc_luminance_decode_table,
    standard_dc_luminance_encode_table,
    value_to_category,
)


class TestBitReaderWriter:

    def test_nominal_case_roundtrip(self):
        writer = BitWriter()
        bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1]
        for bit in bits:
            writer.write_bit(bit)
        data = writer.getvalue()

        reader = BitReader(data)
        recovered = [reader.read_bit() for _ in range(len(bits))]

        assert recovered == bits

    def test_nominal_case_write_bits_matches_manual_bits(self):
        writer = BitWriter()
        writer.write_bits(0b101, 3)
        data = writer.getvalue()

        reader = BitReader(data)
        assert [reader.read_bit() for _ in range(3)] == [1, 0, 1]

    def test_edge_case_read_past_end_raises(self):
        reader = BitReader(b"")
        with pytest.raises(ValueError):
            reader.read_bit()


class TestHuffmanTable:

    def test_nominal_case_encode_decode_roundtrip(self):
        bit_counts = [1, 1] + [0] * 14
        symbols = [7, 9]

        encode_table = build_huffman_encode_table(bit_counts, symbols)
        decode_table = build_huffman_decode_table(bit_counts, symbols)

        writer = BitWriter()
        encode_huffman_symbol(writer, encode_table, 7)
        encode_huffman_symbol(writer, encode_table, 9)
        reader = BitReader(writer.getvalue())

        assert decode_huffman_symbol(reader, decode_table) == 7
        assert decode_huffman_symbol(reader, decode_table) == 9

    def test_edge_case_wrong_bit_counts_length(self):
        with pytest.raises(ValueError):
            build_huffman_decode_table([1, 1], [0, 1])

    def test_edge_case_kraft_inequality_violation(self):
        with pytest.raises(ValueError):
            build_huffman_decode_table([3] + [0] * 15, [0, 1, 2])

    def test_edge_case_encode_unknown_symbol(self):
        encode_table = build_huffman_encode_table([1, 1] + [0] * 14, [7, 9])
        writer = BitWriter()
        with pytest.raises(ValueError):
            encode_huffman_symbol(writer, encode_table, 99)


class TestValueToCategoryAndReceiveExtend:

    def test_nominal_case_positive_and_negative_roundtrip(self):
        for value in (0, 1, -1, 5, -5, 127, -127, 1000, -1000):
            category, bits = value_to_category(value)
            writer = BitWriter()
            writer.write_bits(bits, category)
            reader = BitReader(writer.getvalue())
            recovered = receive_extend(reader, category)
            assert recovered == value

    def test_edge_case_zero_category(self):
        assert value_to_category(0) == (0, 0)


class TestDecodeEncodeBlock:

    @staticmethod
    def _build_tables() -> tuple[dict, dict, dict, dict]:
        dc_symbols = list(range(12))
        dc_bit_counts = [0] * 3 + [12] + [0] * 12

        ac_symbols = sorted(
            {(run << 4) | size for run in range(16) for size in range(1, 11)} | {ZRL, EOB}
        )
        ac_bit_counts = [0] * 7 + [len(ac_symbols)] + [0] * 8

        return (
            build_huffman_encode_table(dc_bit_counts, dc_symbols),
            build_huffman_decode_table(dc_bit_counts, dc_symbols),
            build_huffman_encode_table(ac_bit_counts, ac_symbols),
            build_huffman_decode_table(ac_bit_counts, ac_symbols),
        )

    def test_nominal_case_dc_only_block(self):
        dc_enc, dc_dec, ac_enc, ac_dec = self._build_tables()
        coeffs = [10] + [0] * 63

        writer = BitWriter()
        encode_block(writer, dc_enc, ac_enc, coeffs, prev_dc=0)
        reader = BitReader(writer.getvalue())
        decoded, dc_value = decode_block(reader, dc_dec, ac_dec, prev_dc=0)

        assert decoded == coeffs
        assert dc_value == 10

    def test_nominal_case_differential_dc_across_blocks(self):
        dc_enc, dc_dec, ac_enc, ac_dec = self._build_tables()
        coeffs1 = [10] + [0] * 63
        coeffs2 = [15, 0, 0, 4] + [0] * 60

        writer = BitWriter()
        prev_dc = encode_block(writer, dc_enc, ac_enc, coeffs1, prev_dc=0)
        encode_block(writer, dc_enc, ac_enc, coeffs2, prev_dc=prev_dc)

        reader = BitReader(writer.getvalue())
        decoded1, prev_dc_r = decode_block(reader, dc_dec, ac_dec, prev_dc=0)
        decoded2, _ = decode_block(reader, dc_dec, ac_dec, prev_dc=prev_dc_r)

        assert decoded1 == coeffs1
        assert decoded2 == coeffs2

    def test_nominal_case_zrl_for_long_zero_run(self):
        dc_enc, dc_dec, ac_enc, ac_dec = self._build_tables()
        coeffs = [4] + [0] * 20 + [18] + [0] * 42

        writer = BitWriter()
        encode_block(writer, dc_enc, ac_enc, coeffs, prev_dc=0)
        reader = BitReader(writer.getvalue())
        decoded, _ = decode_block(reader, dc_dec, ac_dec, prev_dc=0)

        assert decoded == coeffs

    def test_edge_case_wrong_coeff_count(self):
        dc_enc, _, ac_enc, _ = self._build_tables()
        writer = BitWriter()
        with pytest.raises(ValueError):
            encode_block(writer, dc_enc, ac_enc, [1, 2, 3], prev_dc=0)

    def test_interop_random_blocks_roundtrip(self):
        dc_enc, dc_dec, ac_enc, ac_dec = self._build_tables()
        rng = random.Random(123)

        prev_dc_encode = 0
        prev_dc_decode = 0
        writer = BitWriter()
        expected_blocks = []
        for _ in range(30):
            n_ac = rng.randint(0, 15)
            coeffs = [rng.randint(-500, 500)] + [0] * 63
            positions = rng.sample(range(1, 64), n_ac)
            for pos in positions:
                coeffs[pos] = rng.randint(-500, 500) or 1
            expected_blocks.append(coeffs)
            prev_dc_encode = encode_block(writer, dc_enc, ac_enc, coeffs, prev_dc_encode)

        reader = BitReader(writer.getvalue())
        for expected in expected_blocks:
            decoded, prev_dc_decode = decode_block(reader, dc_dec, ac_dec, prev_dc_decode)
            assert decoded == expected


class TestStandardLuminanceTables:

    def test_nominal_case_dc_table_symbol_count(self):
        assert sum(STANDARD_DC_LUMINANCE_BITS) == len(STANDARD_DC_LUMINANCE_VALUES) == 12

    def test_nominal_case_ac_table_symbol_count(self):
        assert sum(STANDARD_AC_LUMINANCE_BITS) == len(STANDARD_AC_LUMINANCE_VALUES) == 162

    def test_nominal_case_tables_build_without_kraft_violation(self):
        dc_decode = standard_dc_luminance_decode_table()
        ac_decode = standard_ac_luminance_decode_table()
        assert len(dc_decode) == 12
        assert len(ac_decode) == 162

    def test_interop_encode_decode_block_with_standard_tables(self):
        dc_enc = standard_dc_luminance_encode_table()
        dc_dec = standard_dc_luminance_decode_table()
        ac_enc = standard_ac_luminance_encode_table()
        ac_dec = standard_ac_luminance_decode_table()

        coeffs = [42, 0, 0, 7] + [0] * 60

        writer = BitWriter()
        encode_block(writer, dc_enc, ac_enc, coeffs, prev_dc=0)
        reader = BitReader(writer.getvalue())
        decoded, _ = decode_block(reader, dc_dec, ac_dec, prev_dc=0)

        assert decoded == coeffs
