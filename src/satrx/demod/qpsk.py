from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

ComplexSamples = NDArray[np.complex128]


def downsample_to_symbol_rate(
    iq_samples: ComplexSamples,
    samples_per_symbol: int,
    symbol_offset: int = 0,
) -> ComplexSamples:
    if samples_per_symbol <= 0:
        raise ValueError(f"samples_per_symbol doit etre positif, recu {samples_per_symbol}")
    if not 0 <= symbol_offset < samples_per_symbol:
        raise ValueError(
            f"symbol_offset doit etre dans [0, samples_per_symbol), recu {symbol_offset}"
        )
    return iq_samples[symbol_offset::samples_per_symbol]


def downsample_oqpsk_symbols(
    iq_samples: ComplexSamples,
    samples_per_symbol: int,
    symbol_offset: int = 0,
) -> ComplexSamples:
    if samples_per_symbol <= 0:
        raise ValueError(f"samples_per_symbol doit etre positif, recu {samples_per_symbol}")
    if samples_per_symbol % 2 != 0:
        raise ValueError(
            "samples_per_symbol doit etre pair pour un decalage OQPSK d'un demi-symbole"
        )
    if not 0 <= symbol_offset < samples_per_symbol:
        raise ValueError(
            f"symbol_offset doit etre dans [0, samples_per_symbol), recu {symbol_offset}"
        )

    half = samples_per_symbol // 2
    i_rail = iq_samples.real[symbol_offset::samples_per_symbol]
    q_rail = iq_samples.imag[symbol_offset + half :: samples_per_symbol]

    n = min(len(i_rail), len(q_rail))
    if n == 0:
        raise ValueError("aucun symbole recuperable avec ces parametres de decalage")
    return (i_rail[:n] + 1j * q_rail[:n]).astype(np.complex128)


def slice_qpsk_symbols(symbols: ComplexSamples) -> NDArray[np.uint8]:
    if symbols.size == 0:
        raise ValueError("symbols ne doit pas etre vide")

    bits = np.empty(symbols.size * 2, dtype=np.uint8)
    bits[0::2] = (symbols.real < 0).astype(np.uint8)
    bits[1::2] = (symbols.imag < 0).astype(np.uint8)
    return bits
