"""Generation de bursts GMR-1 (Normal Traffic burst)."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from satrx.security.gmr1.constants import (
    GMR1_NB_ACTIVE_BITS,
    GMR1_NB_DATA,
    GMR1_NB_MIDAMBLE,
    GMR1_NB_TAIL,
    GMR1_NB_TRAINING_SEQ,
)

UInt8Array = NDArray[np.uint8]

_TAIL: UInt8Array = np.zeros(GMR1_NB_TAIL, dtype=np.uint8)


def encode_normal_burst(
    data_bits: UInt8Array,
    training_seq: UInt8Array | None = None,
) -> UInt8Array:
    """Assemble un Normal Traffic burst GMR-1.

    Args:
        data_bits: 78 bits d'information (2 × GMR1_NB_DATA).
        training_seq: sequence d'apprentissage de 64 bits ; utilise
            GMR1_NB_TRAINING_SEQ par defaut.

    Returns:
        Tableau de 148 bits (uint8, valeurs 0/1).
    """
    expected = 2 * GMR1_NB_DATA
    if data_bits.shape != (expected,):
        raise ValueError(
            f"data_bits doit avoir {expected} elements, recu {data_bits.shape}"
        )
    if not np.all((data_bits == 0) | (data_bits == 1)):
        raise ValueError("data_bits doit contenir uniquement des valeurs 0/1")

    ts = GMR1_NB_TRAINING_SEQ if training_seq is None else training_seq
    if ts.shape != (GMR1_NB_MIDAMBLE,):
        raise ValueError(
            f"training_seq doit avoir {GMR1_NB_MIDAMBLE} elements, recu {ts.shape}"
        )

    raw: UInt8Array = np.concatenate([
        _TAIL,
        data_bits[:GMR1_NB_DATA],
        ts,
        data_bits[GMR1_NB_DATA:],
        _TAIL,
    ]).astype(np.uint8)
    assert raw.size == GMR1_NB_ACTIVE_BITS
    return raw


def decode_burst_data(burst: UInt8Array) -> UInt8Array:
    """Extrait les 78 bits de donnees d'un Normal Traffic burst.

    Args:
        burst: tableau de 148 bits.

    Returns:
        Tableau de 78 bits (2 × GMR1_NB_DATA), dans l'ordre
        [premiere_moitie | deuxieme_moitie].
    """
    if burst.shape != (GMR1_NB_ACTIVE_BITS,):
        raise ValueError(
            f"burst doit avoir {GMR1_NB_ACTIVE_BITS} bits, recu {burst.shape}"
        )
    first_half_start = GMR1_NB_TAIL
    first_half_end = GMR1_NB_TAIL + GMR1_NB_DATA
    second_half_start = first_half_end + GMR1_NB_MIDAMBLE
    second_half_end = second_half_start + GMR1_NB_DATA
    return np.concatenate([
        burst[first_half_start:first_half_end],
        burst[second_half_start:second_half_end],
    ])


def generate_idle_burst() -> UInt8Array:
    """Retourne un burst de remplissage (idle) : donnees nulles."""
    return encode_normal_burst(np.zeros(2 * GMR1_NB_DATA, dtype=np.uint8))
