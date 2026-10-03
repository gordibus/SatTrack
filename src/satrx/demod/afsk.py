from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatSamples = NDArray[np.float64]

# Parametres Bell 202 (AX.25 / APRS / liaisons satellite amateur 1200 baud)
BELL202_MARK_HZ: float = 1200.0
BELL202_SPACE_HZ: float = 2200.0
BELL202_BAUD: int = 1200


@dataclass(frozen=True)
class AfskParams:
    """Parametres d'un lien AFSK.

    mark_hz  : frequence correspondant au bit 1
    space_hz : frequence correspondant au bit 0
    baud_rate: debit en symboles/seconde
    msb_first: ordre des bits dans un octet (True = MSB en premier, standard ASCII)
    """

    mark_hz: float
    space_hz: float
    baud_rate: int
    msb_first: bool = True

    def __post_init__(self) -> None:
        if self.mark_hz <= 0 or self.space_hz <= 0:
            raise ValueError("mark_hz et space_hz doivent etre positifs")
        if self.mark_hz == self.space_hz:
            raise ValueError("mark_hz et space_hz doivent etre differents")
        if self.baud_rate <= 0:
            raise ValueError("baud_rate doit etre positif")


BELL202 = AfskParams(
    mark_hz=BELL202_MARK_HZ,
    space_hz=BELL202_SPACE_HZ,
    baud_rate=BELL202_BAUD,
    msb_first=True,
)


def demodulate_afsk_bits(
    samples: FloatSamples,
    sample_rate_hz: float,
    params: AfskParams = BELL202,
) -> list[int]:
    """Demodule un signal AFSK et retourne la sequence de bits.

    Algorithme : corrélateur I/Q (filtre accordé) aux deux fréquences mark/space.
    A chaque position de symbole (centre de la fenetre), le bit vaut 1 si l'energie
    a f_mark est superieure a l'energie a f_space, 0 sinon.

    Args:
        samples       : signal audio normalise (float64, une dimension)
        sample_rate_hz: frequence d'echantillonnage en Hz
        params        : parametres AFSK (defaut : Bell 202)

    Returns:
        Liste d'entiers 0/1, un element par symbole detecte.
    """
    if samples.ndim != 1:
        raise ValueError("samples doit etre un tableau 1D")
    if samples.size == 0:
        raise ValueError("samples ne doit pas etre vide")
    if sample_rate_hz <= 0:
        raise ValueError(f"sample_rate_hz doit etre positif, recu {sample_rate_hz}")

    n = len(samples)
    t = np.arange(n) / sample_rate_hz

    sym_len = int(round(sample_rate_hz / params.baud_rate))
    if sym_len < 2:
        raise ValueError(
            f"sample_rate_hz ({sample_rate_hz}) trop faible pour baud_rate ({params.baud_rate})"
        )

    # Corrélateurs complexes : correlation avec e^{-j2pi*f*t}
    kern = np.ones(sym_len, dtype=np.float64) / sym_len
    corr_mark = np.convolve(
        samples * np.exp(-2j * np.pi * params.mark_hz * t), kern, mode="same"
    )
    corr_space = np.convolve(
        samples * np.exp(-2j * np.pi * params.space_hz * t), kern, mode="same"
    )

    bits: list[int] = []
    half = sym_len // 2
    for center in range(half, n, sym_len):
        m = float(np.abs(corr_mark[center]))
        s = float(np.abs(corr_space[center]))
        bits.append(1 if m >= s else 0)

    return bits


def bits_to_bytes(bits: list[int], msb_first: bool = True) -> bytes:
    """Regroupe une liste de bits en octets.

    Args:
        bits     : liste de 0/1
        msb_first: True = le premier bit du groupe est le MSB (standard ASCII/RS-232)

    Returns:
        bytes contenant les octets reconstitues. Les bits terminaux insuffisants
        pour former un octet complet sont ignores.
    """
    if not all(b in (0, 1) for b in bits):
        raise ValueError("bits ne doit contenir que des valeurs 0 ou 1")

    result = bytearray()
    for i in range(0, len(bits) - 7, 8):
        group = bits[i : i + 8]
        if msb_first:
            val = sum(b << (7 - j) for j, b in enumerate(group))
        else:
            val = sum(b << j for j, b in enumerate(group))
        result.append(val)
    return bytes(result)


def decode_afsk_ascii(
    samples: FloatSamples,
    sample_rate_hz: float,
    params: AfskParams = BELL202,
    errors: str = "replace",
) -> str:
    """Demodule un signal AFSK et retourne la chaine ASCII decodee.

    Combine demodulate_afsk_bits et bits_to_bytes, puis decode en ASCII.

    Args:
        samples       : signal audio normalise (float64, 1D)
        sample_rate_hz: frequence d'echantillonnage en Hz
        params        : parametres AFSK (defaut : Bell 202)
        errors        : strategie de decodage ('replace', 'ignore', 'strict')

    Returns:
        Chaine de caracteres ASCII decodee.
    """
    bits = demodulate_afsk_bits(samples, sample_rate_hz, params)
    raw = bits_to_bytes(bits, msb_first=params.msb_first)
    return raw.decode("ascii", errors=errors)
