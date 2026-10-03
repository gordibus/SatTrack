"""Modulateur GMSK pour simulation GMR-1."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.special import erfc

from satrx.security.gmr1.constants import GMR1_BT, GMR1_MOD_INDEX

ComplexSamples = NDArray[np.complex128]
FloatArray = NDArray[np.float64]
UInt8Array = NDArray[np.uint8]


def gaussian_freq_pulse(bt: float, sps: int, n_sym: int = 5) -> FloatArray:
    """Impulsion frequentielle gaussienne (filtre GMSK).

    L'integrale de la reponse vaut 1/T (un demi-tour de phase par bit).

    Args:
        bt:    produit BT du filtre (ex. 0.3 pour GMR-1/GSM).
        sps:   echantillons par symbole.
        n_sym: longueur du filtre en nombre de periodes symbole.

    Returns:
        Tableau de coefficients FIR de longueur n_sym * sps + 1.
    """
    if bt <= 0:
        raise ValueError("bt doit etre > 0")
    if sps < 1:
        raise ValueError("sps doit etre >= 1")

    n_taps = n_sym * sps + 1
    # t en periodes symbole
    t = np.linspace(-n_sym / 2, n_sym / 2, n_taps)
    # Impulsion frequentielle : difference de deux Q gaussiennes
    alpha = np.sqrt(2 * np.log(2)) / (2 * np.pi * bt)
    h = (
        0.5 * erfc(np.pi / alpha * (t - 0.5))
        - 0.5 * erfc(np.pi / alpha * (t + 0.5))
    )
    # Normalisation : somme = 1 so que le changement de phase total par bit vaille
    # pi * mod_index. Avec le surechantillonnage par repetition (sps copies de ±1),
    # la convolution donne sum(h) * sps, donc : (pi*h/sps) * sum(h) * sps = pi*h*sum(h) = pi/2
    h = h / h.sum()
    result: FloatArray = h.astype(np.float64)
    return result


def gmsk_modulate(
    bits: UInt8Array,
    sps: int = 8,
    bt: float = GMR1_BT,
    mod_index: float = GMR1_MOD_INDEX,
) -> ComplexSamples:
    """Module une sequence de bits en GMSK.

    Args:
        bits:      bits a moduler (valeurs 0/1, uint8).
        sps:       echantillons par symbole.
        bt:        produit BT du filtre gaussien.
        mod_index: indice de modulation h (0.5 pour GMSK standard).

    Returns:
        Tableau complexe de longueur approximative len(bits) * sps.
    """
    if not np.all((bits == 0) | (bits == 1)):
        raise ValueError("bits doit contenir uniquement des valeurs 0/1")
    if sps < 1:
        raise ValueError("sps doit etre >= 1")

    # NRZ : 0 → -1, 1 → +1
    nrz: FloatArray = (2.0 * bits.astype(np.float64) - 1.0)
    # Surechantillonnage par repetition (impulsion rectangulaire NRZ)
    upsampled: FloatArray = np.repeat(nrz, sps)
    # Filtrage gaussien
    h = gaussian_freq_pulse(bt, sps)
    filtered = np.convolve(upsampled, h, mode="full")
    # Increment de phase par echantillon (rad)
    phase_inc: FloatArray = filtered * (np.pi * mod_index / sps)
    # Integration → phase instantanee
    phase: FloatArray = np.cumsum(phase_inc)
    iq: ComplexSamples = np.exp(1j * phase).astype(np.complex128)
    return iq


def to_cs8(iq: ComplexSamples, amplitude: float = 100.0) -> NDArray[np.int8]:
    """Convertit un tableau complexe float en format CS8 (int8 interleave I/Q).

    Args:
        iq:        echantillons complexes normalises (|iq| ~ 1).
        amplitude: facteur d'echelle avant quantification (max 127).

    Returns:
        Tableau int8 de longueur 2 * len(iq) : [I0, Q0, I1, Q1, ...].
    """
    if amplitude <= 0 or amplitude > 127:
        raise ValueError("amplitude doit etre dans ]0, 127]")
    scaled = iq * amplitude
    interleaved = np.empty(2 * len(iq), dtype=np.float64)
    interleaved[0::2] = scaled.real
    interleaved[1::2] = scaled.imag
    return np.clip(np.round(interleaved), -127, 127).astype(np.int8)
