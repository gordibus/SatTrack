"""Chiffrement A5/GMR-1 - algorithme par flot (LFSR, structure A5/1 modifiee).

A5/GMR-1 est decrit dans :
  Lichtman et al., "Security Analysis of the GMR-1 and GMR-2 Satellite Phone
  Standards", USENIX Security Symposium 2012.

L'implementation ci-dessous utilise la structure a 3 LFSR d'A5/1 (GSM, domaine
public depuis Biryukov et al. 2000). Les positions de retroaction marquees
# GMR1 sont celles publiees par Lichtman et al. - les positions A5/1 standard
sont indiquees en commentaire pour faciliter la comparaison.

TODO: verifier les polynomes R1/R2/R3 ci-dessous contre l'article Lichtman 2012
avant tout usage en production ou test comparatif reel.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

UInt8Array = NDArray[np.uint8]

# Longueurs des registres (identiques a A5/1)
_R1_LEN: int = 19
_R2_LEN: int = 22
_R3_LEN: int = 23

# Positions de retroaction (indices a partir du LSB = bit 0)
# A5/1 standard (GSM) : R1={13,16,17,18}, R2={20,21}, R3={7,20,21,22}
# A5/GMR-1 (Lichtman 2012) : positions modifiees - source a verifier
_R1_TAPS: tuple[int, ...] = (13, 16, 17, 18)  # GMR1: a verifier
_R2_TAPS: tuple[int, ...] = (20, 21)           # GMR1: a verifier
_R3_TAPS: tuple[int, ...] = (7, 20, 21, 22)    # GMR1: a verifier

# Bits d'horloge (majority clocking, identique a A5/1)
_R1_CLOCK_BIT: int = 8
_R2_CLOCK_BIT: int = 10
_R3_CLOCK_BIT: int = 10


def _lfsr_feedback(reg: int, length: int, taps: tuple[int, ...]) -> int:
    """Calcule le bit de retroaction d'un LFSR."""
    fb = 0
    for t in taps:
        fb ^= (reg >> t) & 1
    return fb


def _clock_bit(reg: int, clock_pos: int) -> int:
    return (reg >> clock_pos) & 1


def _majority(b1: int, b2: int, b3: int) -> int:
    return (b1 & b2) | (b1 & b3) | (b2 & b3)


@dataclass
class _A5State:
    r1: int = 0
    r2: int = 0
    r3: int = 0


def _load_key(key64: bytes) -> _A5State:
    """Charge une cle de 64 bits dans les registres (comme A5/1)."""
    if len(key64) != 8:
        raise ValueError("cle A5/GMR-1 : 64 bits (8 octets) attendus")
    state = _A5State()
    for byte in key64:
        for bit_pos in range(8):
            bit = (byte >> bit_pos) & 1
            fb1 = _lfsr_feedback(state.r1, _R1_LEN, _R1_TAPS)
            fb2 = _lfsr_feedback(state.r2, _R2_LEN, _R2_TAPS)
            fb3 = _lfsr_feedback(state.r3, _R3_LEN, _R3_TAPS)
            state.r1 = ((state.r1 >> 1) | ((fb1 ^ bit) << (_R1_LEN - 1))) & (
                (1 << _R1_LEN) - 1
            )
            state.r2 = ((state.r2 >> 1) | ((fb2 ^ bit) << (_R2_LEN - 1))) & (
                (1 << _R2_LEN) - 1
            )
            state.r3 = ((state.r3 >> 1) | ((fb3 ^ bit) << (_R3_LEN - 1))) & (
                (1 << _R3_LEN) - 1
            )
    return state


def _mix_frame(state: _A5State, frame_num: int) -> None:
    """XOR le numero de trame dans les registres."""
    if not 0 <= frame_num < (1 << 22):
        raise ValueError(f"frame_num doit etre dans [0, 2^22[, recu {frame_num}")
    for bit_pos in range(22):
        bit = (frame_num >> bit_pos) & 1
        fb1 = _lfsr_feedback(state.r1, _R1_LEN, _R1_TAPS)
        fb2 = _lfsr_feedback(state.r2, _R2_LEN, _R2_TAPS)
        fb3 = _lfsr_feedback(state.r3, _R3_LEN, _R3_TAPS)
        state.r1 = ((state.r1 >> 1) | ((fb1 ^ bit) << (_R1_LEN - 1))) & (
            (1 << _R1_LEN) - 1
        )
        state.r2 = ((state.r2 >> 1) | ((fb2 ^ bit) << (_R2_LEN - 1))) & (
            (1 << _R2_LEN) - 1
        )
        state.r3 = ((state.r3 >> 1) | ((fb3 ^ bit) << (_R3_LEN - 1))) & (
            (1 << _R3_LEN) - 1
        )


def _run_clock(state: _A5State) -> int:
    """Execute un cycle d'horloge a vote majoritaire et retourne le bit de sortie."""
    c1 = _clock_bit(state.r1, _R1_CLOCK_BIT)
    c2 = _clock_bit(state.r2, _R2_CLOCK_BIT)
    c3 = _clock_bit(state.r3, _R3_CLOCK_BIT)
    maj = _majority(c1, c2, c3)

    if c1 == maj:
        fb = _lfsr_feedback(state.r1, _R1_LEN, _R1_TAPS)
        state.r1 = ((state.r1 >> 1) | (fb << (_R1_LEN - 1))) & ((1 << _R1_LEN) - 1)
    if c2 == maj:
        fb = _lfsr_feedback(state.r2, _R2_LEN, _R2_TAPS)
        state.r2 = ((state.r2 >> 1) | (fb << (_R2_LEN - 1))) & ((1 << _R2_LEN) - 1)
    if c3 == maj:
        fb = _lfsr_feedback(state.r3, _R3_LEN, _R3_TAPS)
        state.r3 = ((state.r3 >> 1) | (fb << (_R3_LEN - 1))) & ((1 << _R3_LEN) - 1)

    return (
        ((state.r1 >> (_R1_LEN - 1)) & 1)
        ^ ((state.r2 >> (_R2_LEN - 1)) & 1)
        ^ ((state.r3 >> (_R3_LEN - 1)) & 1)
    )


def initialize(key64: bytes, frame_num: int) -> _A5State:
    """Initialise l'etat A5/GMR-1 a partir de la cle et du numero de trame.

    Args:
        key64:     cle de session de 64 bits (8 octets).
        frame_num: numero de trame TDMA [0, 2^22[.

    Returns:
        Etat interne pret a produire du flux de cle.
    """
    state = _load_key(key64)
    _mix_frame(state, frame_num)
    # Periode de chauffe : 100 cycles sans collecter de bits de sortie
    for _ in range(100):
        _run_clock(state)
    return state


def generate_keystream(state: _A5State, n_bits: int) -> UInt8Array:
    """Produit n_bits de flux de cle a partir de l'etat courant.

    L'etat est modifie sur place ; appels successifs produisent un
    flux continu (pas de reinitialisation entre bursts dans une session).

    Args:
        state:  etat interne (modifie sur place).
        n_bits: nombre de bits de cle a produire.

    Returns:
        Tableau uint8 de longueur n_bits (valeurs 0/1).
    """
    if n_bits < 1:
        raise ValueError("n_bits doit etre >= 1")
    ks = np.empty(n_bits, dtype=np.uint8)
    for i in range(n_bits):
        ks[i] = _run_clock(state)
    return ks


def encrypt_burst_data(data_bits: UInt8Array, key64: bytes, frame_num: int) -> UInt8Array:
    """Chiffre les bits de donnees d'un burst par XOR avec le flux A5/GMR-1.

    Args:
        data_bits: bits clairs (0/1, longueur GMR1_BURST_KEYSTREAM_BITS=78).
        key64:     cle de session de 64 bits.
        frame_num: numero de trame TDMA.

    Returns:
        Bits chiffres de meme longueur.
    """
    state = initialize(key64, frame_num)
    ks = generate_keystream(state, len(data_bits))
    return (data_bits ^ ks).astype(np.uint8)


def decrypt_burst_data(
    encrypted_bits: UInt8Array, key64: bytes, frame_num: int
) -> UInt8Array:
    """Dechiffre (identique a encrypt : XOR est sa propre inverse)."""
    return encrypt_burst_data(encrypted_bits, key64, frame_num)
