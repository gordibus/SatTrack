from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

ComplexSamples = NDArray[np.complex128]

# Recouvrement de timing non-adaptatif par maximisation d'energie (non-data-aided) : pour
# un signal mis en forme (RRC ou equivalent), l'instant d'echantillonnage correct maximise
# l'energie moyenne des symboles extraits (ISI minimale) ; un mauvais instant l'attenue par
# interference inter-symboles. Approche par bloc (pas de poursuite continue d'une derive
# d'horloge sur un enregistrement tres long), choisie apres qu'une premiere tentative de
# boucle de Gardner adaptative (PLL) ait converge de façon peu fiable/instable meme apres
# correction d'un bug de signe - cette methode est plus simple a garantir correcte.


def _extract_at_offset(samples: ComplexSamples, samples_per_symbol: int, offset: float) -> ComplexSamples:
    positions = offset + np.arange(0, len(samples) - samples_per_symbol, samples_per_symbol, dtype=np.float64)
    idx = np.floor(positions).astype(np.int64)
    frac = positions - idx
    valid = idx + 1 < len(samples)
    idx = idx[valid]
    frac = frac[valid]
    values = (1.0 - frac) * samples[idx] + frac * samples[idx + 1]
    result: ComplexSamples = values.astype(np.complex128)
    return result


def estimate_symbol_timing_offset(
    samples: ComplexSamples,
    samples_per_symbol: int,
    n_test_offsets: int = 32,
) -> float:
    if samples.size == 0:
        raise ValueError("samples ne doit pas etre vide")
    if samples_per_symbol < 2:
        raise ValueError(f"samples_per_symbol doit etre >= 2, recu {samples_per_symbol}")
    if n_test_offsets < 2:
        raise ValueError(f"n_test_offsets doit etre >= 2, recu {n_test_offsets}")
    if len(samples) < samples_per_symbol * 4:
        raise ValueError("samples trop court pour estimer un timing fiable (au moins 4 symboles requis)")

    best_offset = 0.0
    best_energy = -1.0
    for i in range(n_test_offsets):
        frac = i * samples_per_symbol / n_test_offsets
        values = _extract_at_offset(samples, samples_per_symbol, frac)
        if values.size == 0:
            continue
        energy = float(np.mean(np.abs(values) ** 2))
        if energy > best_energy:
            best_energy = energy
            best_offset = frac

    return best_offset


def extract_symbols_at_offset(
    samples: ComplexSamples,
    samples_per_symbol: int,
    offset: float,
) -> ComplexSamples:
    if samples.size == 0:
        raise ValueError("samples ne doit pas etre vide")
    if samples_per_symbol < 2:
        raise ValueError(f"samples_per_symbol doit etre >= 2, recu {samples_per_symbol}")
    if not 0.0 <= offset < samples_per_symbol:
        raise ValueError(f"offset doit etre dans [0, {samples_per_symbol}), recu {offset}")

    return _extract_at_offset(samples, samples_per_symbol, offset)
