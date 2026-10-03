from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from satrx.decode.jpeg_entropy import BitReader, BitWriter, decode_block, encode_block
from satrx.image.dct import block_to_zigzag, dct_8x8, dequantize, idct_8x8, quantize, zigzag_to_block

_BLOCK_SIZE = 8


def _check_dimensions(width_px: int, height_px: int) -> tuple[int, int]:
    if width_px <= 0 or height_px <= 0:
        raise ValueError(f"width_px et height_px doivent etre positifs, recus {width_px}x{height_px}")
    if width_px % _BLOCK_SIZE != 0 or height_px % _BLOCK_SIZE != 0:
        raise ValueError(
            f"width_px ({width_px}) et height_px ({height_px}) doivent etre des multiples de {_BLOCK_SIZE}"
        )
    return width_px // _BLOCK_SIZE, height_px // _BLOCK_SIZE


def decode_mcu_image(
    reader: BitReader,
    dc_table: dict[tuple[int, int], int],
    ac_table: dict[tuple[int, int], int],
    quant_table: NDArray[np.float64],
    width_px: int,
    height_px: int,
) -> NDArray[np.uint8]:
    n_blocks_x, n_blocks_y = _check_dimensions(width_px, height_px)

    image = np.zeros((height_px, width_px), dtype=np.uint8)
    prev_dc = 0
    for by in range(n_blocks_y):
        for bx in range(n_blocks_x):
            coeffs, prev_dc = decode_block(reader, dc_table, ac_table, prev_dc)
            block = zigzag_to_block([float(c) for c in coeffs])
            dequantized = dequantize(block, quant_table)
            spatial = idct_8x8(dequantized)
            pixels = np.clip(spatial + 128.0, 0, 255).astype(np.uint8)
            image[
                by * _BLOCK_SIZE : (by + 1) * _BLOCK_SIZE, bx * _BLOCK_SIZE : (bx + 1) * _BLOCK_SIZE
            ] = pixels
    return image


def encode_mcu_image(
    writer: BitWriter,
    dc_table: dict[int, tuple[int, int]],
    ac_table: dict[int, tuple[int, int]],
    quant_table: NDArray[np.float64],
    image: NDArray[np.uint8],
) -> None:
    height_px, width_px = image.shape
    n_blocks_x, n_blocks_y = _check_dimensions(width_px, height_px)

    prev_dc = 0
    for by in range(n_blocks_y):
        for bx in range(n_blocks_x):
            block = image[
                by * _BLOCK_SIZE : (by + 1) * _BLOCK_SIZE, bx * _BLOCK_SIZE : (bx + 1) * _BLOCK_SIZE
            ].astype(np.float64) - 128.0
            coeffs = dct_8x8(block)
            quantized = quantize(coeffs, quant_table)
            zigzag = [int(v) for v in block_to_zigzag(quantized)]
            prev_dc = encode_block(writer, dc_table, ac_table, zigzag, prev_dc)
