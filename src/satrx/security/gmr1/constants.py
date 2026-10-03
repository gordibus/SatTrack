"""Constantes physiques GMR-1 - ETSI TS 101 376-5-6 / osmocomGMR (Welte 2011)."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Couche physique
GMR1_SYM_RATE: int = 23_400       # sym/s
GMR1_BT: float = 0.3              # produit BT filtre gaussien GMSK
GMR1_MOD_INDEX: float = 0.5       # indice de modulation h

# Trame TDMA
GMR1_FRAME_SLOTS: int = 8
GMR1_SLOT_DURATION_S: float = 576.9e-6   # ~577 µs (meme grille que GSM)
GMR1_FRAME_DURATION_S: float = GMR1_SLOT_DURATION_S * GMR1_FRAME_SLOTS

# Burst Normal Traffic (ETSI TS 101 376-5-6 §8)
# Disposition : 3 tail | 39 data | 64 midamble | 39 data | 3 tail = 148 bits actifs
GMR1_NB_TAIL: int = 3
GMR1_NB_DATA: int = 39    # bits par demi-burst
GMR1_NB_MIDAMBLE: int = 64
GMR1_NB_ACTIVE_BITS: int = (
    2 * GMR1_NB_TAIL + 2 * GMR1_NB_DATA + GMR1_NB_MIDAMBLE
)  # 148

# Flux de clé produit par A5/GMR-1 par burst
GMR1_BURST_KEYSTREAM_BITS: int = 2 * GMR1_NB_DATA  # 78 bits

# Sequence d'apprentissage du burst normal (64 bits)
# TODO: remplacer par la vraie sequence de l'ETSI TS 101 376-5-6 Table 8.x
# Cette sequence PN sert uniquement a la simulation synthetique.
# Ne pas l'utiliser pour la correlation sur un vrai signal sans la valider d'abord.
GMR1_NB_TRAINING_SEQ: NDArray[np.uint8] = np.array(
    [
        1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1,
        1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0,
        1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1,
        1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0,
    ],
    dtype=np.uint8,
)
assert GMR1_NB_TRAINING_SEQ.size == GMR1_NB_MIDAMBLE
