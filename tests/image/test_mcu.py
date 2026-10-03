import numpy as np
import pytest

from satrx.decode.jpeg_entropy import (
    EOB,
    ZRL,
    BitReader,
    BitWriter,
    build_huffman_decode_table,
    build_huffman_encode_table,
)
from satrx.image.mcu import decode_mcu_image, encode_mcu_image


def _build_tables():
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


def _gradient_image(width: int, height: int) -> np.ndarray:
    image = np.zeros((height, width), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            image[y, x] = (x * 8 + y * 4) % 256
    return image


class TestMcuImageRoundtrip:

    def test_nominal_case_16x16_gradient(self):
        dc_enc, dc_dec, ac_enc, ac_dec = _build_tables()
        quant_table = np.full((8, 8), 8.0)
        image = _gradient_image(16, 16)

        writer = BitWriter()
        encode_mcu_image(writer, dc_enc, ac_enc, quant_table, image)
        reader = BitReader(writer.getvalue())
        decoded = decode_mcu_image(reader, dc_dec, ac_dec, quant_table, width_px=16, height_px=16)

        assert decoded.shape == (16, 16)
        diff = np.abs(image.astype(int) - decoded.astype(int))
        assert diff.max() <= 4  # tolerance de quantification JPEG a perte

    def test_nominal_case_single_block_flat_image(self):
        dc_enc, dc_dec, ac_enc, ac_dec = _build_tables()
        quant_table = np.full((8, 8), 4.0)
        image = np.full((8, 8), 100, dtype=np.uint8)

        writer = BitWriter()
        encode_mcu_image(writer, dc_enc, ac_enc, quant_table, image)
        reader = BitReader(writer.getvalue())
        decoded = decode_mcu_image(reader, dc_dec, ac_dec, quant_table, width_px=8, height_px=8)

        assert np.allclose(decoded, 100, atol=2)

    def test_edge_case_dimensions_not_multiple_of_8(self):
        dc_enc, _, ac_enc, _ = _build_tables()
        writer = BitWriter()
        quant_table = np.full((8, 8), 8.0)
        image = np.zeros((10, 16), dtype=np.uint8)

        with pytest.raises(ValueError):
            encode_mcu_image(writer, dc_enc, ac_enc, quant_table, image)

    def test_edge_case_decode_invalid_dimensions(self):
        _, dc_dec, _, ac_dec = _build_tables()
        reader = BitReader(b"\x00")
        quant_table = np.full((8, 8), 8.0)

        with pytest.raises(ValueError):
            decode_mcu_image(reader, dc_dec, ac_dec, quant_table, width_px=15, height_px=8)

    def test_interop_multi_block_preserves_prev_dc_chain(self):
        # verifie que le DC differentiel s'enchaine correctement entre blocs (raster order)
        dc_enc, dc_dec, ac_enc, ac_dec = _build_tables()
        quant_table = np.full((8, 8), 16.0)
        image = np.zeros((16, 8), dtype=np.uint8)
        image[:8, :] = 50
        image[8:, :] = 200

        writer = BitWriter()
        encode_mcu_image(writer, dc_enc, ac_enc, quant_table, image)
        reader = BitReader(writer.getvalue())
        decoded = decode_mcu_image(reader, dc_dec, ac_dec, quant_table, width_px=8, height_px=16)

        assert decoded[:8, :].mean() < decoded[8:, :].mean()
