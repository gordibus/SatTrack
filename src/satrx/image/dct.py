from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

_BLOCK_SIZE = 8

_ALPHA = np.array([1.0 / np.sqrt(2) if u == 0 else 1.0 for u in range(_BLOCK_SIZE)])

_COS_TABLE = np.array(
    [
        [np.cos((2 * x + 1) * u * np.pi / 16) for u in range(_BLOCK_SIZE)]
        for x in range(_BLOCK_SIZE)
    ]
)

# Ordre zigzag standard JPEG (ITU T.81) pour un bloc 8x8 : structurel, independant
# des tables de Huffman/quantification donc valable quel que soit l'encodeur.
ZIGZAG_ORDER = [
    0, 1, 8, 16, 9, 2, 3, 10,
    17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
]  # fmt: skip

# Table de quantification luminance standard JPEG (ITU T.81 Annexe K.1) et formule
# d'echelle qualite IJG : confirmees comme utilisees telles quelles par l'encodeur LRPT
# Meteor-M (recherche du 16/08/2026, source : artlav/meteor_decoder, fichier met_jpg.pas,
# fonction fill_dqt_by_q). Le parametre de qualite reel transmis dans le flux LRPT n'est
# pas connu ici - a lire depuis le flux quand le decodage complet sera possible.
STANDARD_LUMINANCE_QUANT_TABLE = np.array(
    [
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99,
    ],  # fmt: skip
    dtype=np.float64,
).reshape(8, 8)


def scale_quantization_table(quality: int, base_table: NDArray[np.float64] = STANDARD_LUMINANCE_QUANT_TABLE) -> NDArray[np.float64]:
    if not 1 <= quality <= 100:
        raise ValueError(f"quality doit etre dans [1, 100], recu {quality}")

    factor = 5000.0 / quality if quality < 50 else 200.0 - 2.0 * quality
    scaled = np.round(factor / 100.0 * base_table)
    result: NDArray[np.float64] = np.clip(scaled, 1, 255)
    return result


def _check_block_shape(block: NDArray[np.float64], name: str) -> None:
    if block.shape != (_BLOCK_SIZE, _BLOCK_SIZE):
        raise ValueError(f"{name} doit etre de forme (8, 8), recu {block.shape}")


def dct_8x8(block: NDArray[np.float64]) -> NDArray[np.float64]:
    _check_block_shape(block, "block")
    transformed = _COS_TABLE.T @ block @ _COS_TABLE
    result: NDArray[np.float64] = 0.25 * _ALPHA[:, None] * _ALPHA[None, :] * transformed
    return result


def idct_8x8(coeffs: NDArray[np.float64]) -> NDArray[np.float64]:
    _check_block_shape(coeffs, "coeffs")
    weighted = _ALPHA[:, None] * _ALPHA[None, :] * coeffs
    result: NDArray[np.float64] = 0.25 * (_COS_TABLE @ weighted @ _COS_TABLE.T)
    return result


def zigzag_to_block(coeffs: list[float]) -> NDArray[np.float64]:
    if len(coeffs) != _BLOCK_SIZE * _BLOCK_SIZE:
        raise ValueError(f"coeffs doit contenir 64 valeurs, recu {len(coeffs)}")

    block = np.zeros((_BLOCK_SIZE, _BLOCK_SIZE), dtype=np.float64)
    for zz_index, value in enumerate(coeffs):
        pos = ZIGZAG_ORDER[zz_index]
        block[pos // _BLOCK_SIZE, pos % _BLOCK_SIZE] = value
    return block


def block_to_zigzag(block: NDArray[np.float64]) -> list[float]:
    _check_block_shape(block, "block")
    flat = block.reshape(-1)
    return [float(flat[pos]) for pos in ZIGZAG_ORDER]


def dequantize(coeffs: NDArray[np.float64], quant_table: NDArray[np.float64]) -> NDArray[np.float64]:
    _check_block_shape(coeffs, "coeffs")
    _check_block_shape(quant_table, "quant_table")
    return coeffs * quant_table


def quantize(coeffs: NDArray[np.float64], quant_table: NDArray[np.float64]) -> NDArray[np.float64]:
    _check_block_shape(coeffs, "coeffs")
    _check_block_shape(quant_table, "quant_table")
    return np.round(coeffs / quant_table)
