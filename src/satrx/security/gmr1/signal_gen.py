"""Generateur de signal GMR-1 simule (IQ synthetique, environnement lab isole).

Usage :
    from satrx.security.gmr1.signal_gen import generate_gmr1_signal, save_gmr1_iq
    iq = generate_gmr1_signal(n_frames=4, key64=bytes(8), sps=8)
    save_gmr1_iq(iq, "data/raw/gmr1_sim.cs8", sps=8)
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from satrx.security.gmr1 import a5gmr1, burst
from satrx.security.gmr1.constants import (
    GMR1_BURST_KEYSTREAM_BITS,
    GMR1_FRAME_SLOTS,
    GMR1_SYM_RATE,
)
from satrx.security.gmr1.gmsk import gmsk_modulate, to_cs8

ComplexSamples = NDArray[np.complex128]
UInt8Array = NDArray[np.uint8]

# Numero de trame TDMA de depart par defaut
_DEFAULT_FRAME_START: int = 0

# Slot occupe par le signal simule (les autres sont des idle bursts)
_ACTIVE_SLOT: int = 0


@dataclass
class Gmr1SignalSpec:
    """Parametres du signal GMR-1 simule."""

    n_frames: int
    key64: bytes
    sps: int
    bt: float
    frame_num_start: int
    plaintext_frames: frozenset[int]  # indices de trames emises en clair (sans chiffrement)
    snr_db: float | None  # None = pas de bruit ajoute


def _random_data_bits(rng: np.random.Generator) -> UInt8Array:
    return rng.integers(0, 2, size=GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)


def generate_gmr1_signal(
    n_frames: int,
    key64: bytes,
    sps: int = 8,
    bt: float = 0.3,
    frame_num_start: int = _DEFAULT_FRAME_START,
    plaintext_frames: frozenset[int] | None = None,
    snr_db: float | None = None,
    rng: np.random.Generator | None = None,
) -> ComplexSamples:
    """Genere n_frames trames TDMA GMR-1 modulees en GMSK.

    Seul GMR1_FRAME_SLOTS-1 slots sur 8 sont des idle bursts ; le slot 0
    porte les donnees (chiffrees si le numero de trame n'est pas dans
    plaintext_frames, claires sinon).

    Args:
        n_frames:        nombre de trames TDMA a generer.
        key64:           cle de session A5/GMR-1 (8 octets = 64 bits).
        sps:             echantillons par symbole.
        bt:              produit BT du filtre gaussien.
        frame_num_start: premier numero de trame TDMA.
        plaintext_frames: ensemble d'indices de trames (relatifs, 0-base)
                         emises en clair - utile pour la demo chiffre/clair.
                         None = tout chiffre.
        snr_db:          rapport signal/bruit en dB ajoute (None = aucun bruit).
        rng:             generateur aleatoire (reproductible si fourni).

    Returns:
        Tableau complexe float64 representant le signal IQ.
    """
    if n_frames < 1:
        raise ValueError("n_frames doit etre >= 1")
    if len(key64) != 8:
        raise ValueError("key64 doit contenir exactement 8 octets")
    if sps < 2:
        raise ValueError("sps doit etre >= 2")

    _rng = rng if rng is not None else np.random.default_rng(42)
    _plaintext = plaintext_frames if plaintext_frames is not None else frozenset()

    segments: list[ComplexSamples] = []

    for frame_idx in range(n_frames):
        frame_num = frame_num_start + frame_idx
        for slot_idx in range(GMR1_FRAME_SLOTS):
            if slot_idx != _ACTIVE_SLOT:
                data = np.zeros(GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)
            else:
                data = _random_data_bits(_rng)
                if frame_idx not in _plaintext:
                    data = a5gmr1.encrypt_burst_data(data, key64, frame_num)

            b = burst.encode_normal_burst(data)
            iq = gmsk_modulate(b, sps=sps, bt=bt)
            segments.append(iq)

    signal: ComplexSamples = np.concatenate(segments)

    if snr_db is not None:
        signal_power = np.mean(np.abs(signal) ** 2)
        noise_power = signal_power / (10.0 ** (snr_db / 10.0))
        noise = _rng.standard_normal(len(signal)) + 1j * _rng.standard_normal(
            len(signal)
        )
        noise = noise * np.sqrt(noise_power / 2.0)
        signal = signal + noise

    return signal


def save_gmr1_iq(
    signal: ComplexSamples,
    output_path: str | Path,
    sps: int,
    center_freq_hz: float = 1_621_250_000.0,
    note: str = "simulation GMR-1 lab isole",
) -> None:
    """Sauvegarde le signal simule au format CS8 + sidecar JSON.

    Le format CS8 est identique a celui produit par record_iq (acquisition),
    ce qui permet de le rejouer dans le pipeline de demodulation existant.

    Args:
        signal:         tableau IQ complexe.
        output_path:    chemin du fichier .cs8 de sortie.
        sps:            echantillons par symbole (determine le sample_rate).
        center_freq_hz: frequence centrale (pour les metadonnees).
        note:           champ libre dans le sidecar JSON.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    cs8 = to_cs8(signal)
    path.write_bytes(cs8.tobytes())

    sample_rate = GMR1_SYM_RATE * sps
    meta = {
        "center_freq_hz": center_freq_hz,
        "sample_rate_sps": sample_rate,
        "n_samples": len(signal),
        "format": "cs8",
        "note": note,
        "source": "simulation",
    }
    path.with_suffix(".cs8.json").write_text(json.dumps(meta, indent=2))
