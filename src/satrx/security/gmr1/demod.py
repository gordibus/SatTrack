"""Demodulateur GMR-1 - detection differentielle GMSK + synchronisation de burst.

Pipeline :
  IQ complexe
  → difference de phase echantillon par echantillon
  → integration sur sps echantillons → bits mous (float)
  → correlation avec la sequence d'apprentissage (midamble)
  → extraction des bits de donnees de chaque burst
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from satrx.security.gmr1.constants import (
    GMR1_BURST_KEYSTREAM_BITS,
    GMR1_FRAME_SLOTS,
    GMR1_NB_ACTIVE_BITS,
    GMR1_NB_DATA,
    GMR1_NB_MIDAMBLE,
    GMR1_NB_TAIL,
    GMR1_NB_TRAINING_SEQ,
)

ComplexSamples = NDArray[np.complex128]
FloatArray = NDArray[np.float64]
UInt8Array = NDArray[np.uint8]

# Nombre de periodes symbole couverts par le filtre gaussien (doit correspondre
# a la valeur utilisee dans gmsk.py::gaussian_freq_pulse)
_FILTER_N_SYM: int = 5

# Offset du midamble dans un burst (en bits depuis le debut)
_MIDAMBLE_OFFSET: int = GMR1_NB_TAIL + GMR1_NB_DATA   # 42


@dataclass
class DemodResult:
    """Resultat de la demodulation d'un burst."""

    frame_idx: int
    slot_idx: int
    data_bits: UInt8Array      # 78 bits (2 × GMR1_NB_DATA), decisions binaires
    soft_bits: FloatArray      # memes 78 bits en valeurs molles (pour LLR)
    midamble_corr: float       # pic de correlation du midamble (indicateur de qualite)


def gmsk_demodulate_soft(
    iq: ComplexSamples,
    sps: int,
    timing_offset: int = 0,
) -> FloatArray:
    """Detection differentielle GMSK - retourne des bits mous (phase integree/symbole).

    Chaque symbole produit une valeur : positive → bit 1, negative → bit 0.
    La decision binaire s'obtient par seuillage a 0.

    Args:
        iq:            echantillons IQ complexes.
        sps:           echantillons par symbole.
        timing_offset: decalage d'echantillonnage [0, sps[, pour l'alignement
                       au bon instant de symbole (0 pour un signal simule).

    Returns:
        Tableau float de longueur approximative len(iq) // sps.
    """
    if sps < 2:
        raise ValueError("sps doit etre >= 2")
    if not 0 <= timing_offset < sps:
        raise ValueError(f"timing_offset doit etre dans [0, sps[, recu {timing_offset}")

    # Difference de phase entre echantillons consecutifs
    phase_diff: FloatArray = np.angle(iq[1:] * np.conj(iq[:-1]))

    # Compensation du delai de groupe du filtre gaussien (n_sym/2 periodes symbole)
    group_delay = (_FILTER_N_SYM // 2) * sps + timing_offset
    if group_delay >= len(phase_diff):
        raise ValueError("Signal trop court par rapport au delai de groupe du filtre")
    phase_diff = phase_diff[group_delay:]

    # Integration sur sps echantillons par symbole
    n_sym = len(phase_diff) // sps
    segments = phase_diff[: n_sym * sps].reshape(n_sym, sps)
    soft: FloatArray = segments.sum(axis=1)
    return soft


def find_best_timing_offset(
    iq: ComplexSamples,
    sps: int,
    training_seq: UInt8Array | None = None,
) -> int:
    """Trouve le decalage de timing optimal par maximisation de la correlation midamble.

    Teste les sps decalages possibles et retourne celui qui maximise le pic
    de correlation de la sequence d'apprentissage.

    Args:
        iq:           signal IQ.
        sps:          echantillons par symbole.
        training_seq: sequence de reference (GMR1_NB_TRAINING_SEQ par defaut).

    Returns:
        Decalage optimal dans [0, sps[.
    """
    ts = GMR1_NB_TRAINING_SEQ if training_seq is None else training_seq
    ref: FloatArray = 2.0 * ts.astype(np.float64) - 1.0

    best_offset = 0
    best_peak: float = -np.inf

    for offset in range(sps):
        soft = gmsk_demodulate_soft(iq, sps, timing_offset=offset)
        if len(soft) < GMR1_NB_ACTIVE_BITS:
            continue
        corr: FloatArray = np.correlate(soft, ref, mode="valid")
        peak = float(np.max(np.abs(corr)))
        if peak > best_peak:
            best_peak = peak
            best_offset = offset

    return best_offset


def _midamble_ref(training_seq: UInt8Array) -> FloatArray:
    return 2.0 * training_seq.astype(np.float64) - 1.0


def locate_midambles(
    soft: FloatArray,
    n_bursts: int,
    training_seq: UInt8Array | None = None,
) -> list[int]:
    """Localise les positions des midambles dans le flux de bits mous.

    La correlation est calculee sur l'ensemble du flux ; les `n_bursts` pics
    les plus forts sont retenus, triés par position croissante.

    Args:
        soft:     flux de bits mous (sortie de gmsk_demodulate_soft).
        n_bursts: nombre de bursts attendus.
        training_seq: sequence d'apprentissage (GMR1_NB_TRAINING_SEQ par defaut).

    Returns:
        Liste de n_bursts positions (indice dans soft du premier bit du midamble).
    """
    ts = GMR1_NB_TRAINING_SEQ if training_seq is None else training_seq
    if ts.shape != (GMR1_NB_MIDAMBLE,):
        raise ValueError(
            f"training_seq doit avoir {GMR1_NB_MIDAMBLE} elements"
        )
    ref = _midamble_ref(ts)
    corr: FloatArray = np.correlate(soft, ref, mode="valid")
    abs_corr = np.abs(corr)

    # Extraction des n_bursts pics avec suppression des voisins (fenetre = GMR1_NB_ACTIVE_BITS/2)
    min_distance = GMR1_NB_ACTIVE_BITS // 2
    peaks: list[int] = []
    remaining = abs_corr.copy()
    for _ in range(n_bursts):
        if remaining.max() <= 0:
            break
        pos = int(np.argmax(remaining))
        peaks.append(pos)
        lo = max(0, pos - min_distance)
        hi = min(len(remaining), pos + min_distance)
        remaining[lo:hi] = 0.0

    return sorted(peaks)


def extract_data_from_burst(
    soft: FloatArray,
    midamble_pos: int,
) -> tuple[UInt8Array, FloatArray]:
    """Extrait les bits de donnees d'un burst a partir de la position du midamble.

    Args:
        soft:         flux de bits mous.
        midamble_pos: position du premier bit du midamble dans soft.

    Returns:
        (data_bits, soft_data) : bits binaires (0/1) et valeurs molles
        correspondant aux 78 bits de donnees (2 × GMR1_NB_DATA).
    """
    burst_start = midamble_pos - _MIDAMBLE_OFFSET
    if burst_start < 0:
        raise ValueError(
            f"midamble_pos={midamble_pos} trop proche du debut du flux "
            f"(burst_start={burst_start} < 0)"
        )
    first_data_start = burst_start + GMR1_NB_TAIL
    first_data_end = first_data_start + GMR1_NB_DATA
    second_data_start = midamble_pos + GMR1_NB_MIDAMBLE
    second_data_end = second_data_start + GMR1_NB_DATA

    if second_data_end > len(soft):
        raise ValueError(
            f"Flux trop court pour extraire le burst a midamble_pos={midamble_pos}"
        )

    soft_data: FloatArray = np.concatenate([
        soft[first_data_start:first_data_end],
        soft[second_data_start:second_data_end],
    ])
    data_bits: UInt8Array = (soft_data > 0).astype(np.uint8)
    return data_bits, soft_data


def demodulate_signal(
    iq: ComplexSamples,
    sps: int,
    n_frames: int,
    training_seq: UInt8Array | None = None,
    timing_offset: int | None = None,
) -> list[DemodResult]:
    """Pipeline de demodulation GMR-1 complet.

    Args:
        iq:            signal IQ issu de generate_gmr1_signal ou d'une capture.
        sps:           echantillons par symbole.
        n_frames:      nombre de trames TDMA attendues.
        training_seq:  sequence d'apprentissage (GMR1_NB_TRAINING_SEQ par defaut).
        timing_offset: decalage de timing [0, sps[ ; None = auto (recherche exhaustive).

    Returns:
        Liste de DemodResult, un par burst detecte (dans l'ordre de la trame).
    """
    if sps < 2:
        raise ValueError("sps doit etre >= 2")
    if n_frames < 1:
        raise ValueError("n_frames doit etre >= 1")

    ts = GMR1_NB_TRAINING_SEQ if training_seq is None else training_seq

    offset: int
    if timing_offset is None:
        offset = find_best_timing_offset(iq, sps, ts)
    else:
        if not 0 <= timing_offset < sps:
            raise ValueError(f"timing_offset doit etre dans [0, sps[")
        offset = timing_offset

    soft = gmsk_demodulate_soft(iq, sps, timing_offset=offset)

    n_bursts = n_frames * GMR1_FRAME_SLOTS
    midamble_positions = locate_midambles(soft, n_bursts, ts)

    ref = _midamble_ref(ts)

    results: list[DemodResult] = []
    for burst_idx, mid_pos in enumerate(midamble_positions):
        try:
            data_bits, soft_data = extract_data_from_burst(soft, mid_pos)
        except ValueError:
            continue

        # Correlation au pic pour la qualite
        mid_end = mid_pos + GMR1_NB_MIDAMBLE
        if mid_end <= len(soft):
            mid_soft = soft[mid_pos:mid_end]
            corr_val = float(np.dot(mid_soft / (np.linalg.norm(mid_soft) + 1e-12), ref))
        else:
            corr_val = 0.0

        frame_idx = burst_idx // GMR1_FRAME_SLOTS
        slot_idx = burst_idx % GMR1_FRAME_SLOTS

        results.append(
            DemodResult(
                frame_idx=frame_idx,
                slot_idx=slot_idx,
                data_bits=data_bits,
                soft_bits=soft_data,
                midamble_corr=corr_val,
            )
        )

    return results
