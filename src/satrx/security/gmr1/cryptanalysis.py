"""Cryptanalyse A5/GMR-1 - attaque par correlation sur les registres LFSR.

Methode implementee :
  1. Recuperation du flux de cle par XOR clair/chiffre (attaque a texte clair connu).
  2. Recherche exhaustive vectorisee de l'etat initial de chaque LFSR en mode autonome
     (free-running), par maximisation de la correlation avec le flux de cle connu.
  3. Verification de l'etat (R1, R2, R3) retrouve par simulation complete avec
     clocking majoritaire.

Reference : Lichtman et al., "Security Analysis of the GMR-1 and GMR-2 Satellite
Phone Standards", USENIX Security Symposium 2012.

Note sur les etats retrouves : cet algorithme retrouve les etats des LFSRs APRES
initialisation (chargement de cle + melange de trame + 100 cycles de chauffe).
Ces etats permettent de dechiffrer la trame courante, mais ne donnent pas directement
la cle de session de 64 bits - ce qui necessite une attaque complementaire sur le
mecanisme de chargement de cle (hors perimetre de cette demonstration).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from satrx.security.gmr1.a5gmr1 import (
    _R1_CLOCK_BIT,
    _R1_LEN,
    _R1_TAPS,
    _R2_CLOCK_BIT,
    _R2_LEN,
    _R2_TAPS,
    _R3_CLOCK_BIT,
    _R3_LEN,
    _R3_TAPS,
    _A5State,
    _lfsr_feedback,
    _majority,
    _run_clock,
)

UInt8Array = NDArray[np.uint8]
FloatArray = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Etape 1 : recuperation du flux de cle (attaque a texte clair connu)
# ---------------------------------------------------------------------------

def recover_keystream(plaintext: UInt8Array, ciphertext: UInt8Array) -> UInt8Array:
    """Recupere le flux de cle par XOR clair/chiffre (trivial).

    Args:
        plaintext:  bits clairs (0/1).
        ciphertext: bits chiffres correspondants (meme longueur).

    Returns:
        Flux de cle de meme longueur.
    """
    if plaintext.shape != ciphertext.shape:
        raise ValueError(
            f"plaintext et ciphertext doivent avoir la meme forme : "
            f"{plaintext.shape} vs {ciphertext.shape}"
        )
    if not np.all((plaintext == 0) | (plaintext == 1)):
        raise ValueError("plaintext doit contenir uniquement des valeurs 0/1")
    if not np.all((ciphertext == 0) | (ciphertext == 1)):
        raise ValueError("ciphertext doit contenir uniquement des valeurs 0/1")
    return (plaintext ^ ciphertext).astype(np.uint8)


# ---------------------------------------------------------------------------
# Etape 2 : recherche exhaustive vectorisee de l'etat LFSR
# ---------------------------------------------------------------------------

def _all_lfsr_outputs(
    reg_len: int,
    taps: tuple[int, ...],
    n_bits: int,
) -> NDArray[np.uint8]:
    """Genere en parallele les n_bits premiers bits de sortie de tous les 2^reg_len
    etats initiaux d'un LFSR en mode autonome (sans clocking majoritaire).

    Args:
        reg_len: longueur du registre en bits.
        taps:    positions de retroaction.
        n_bits:  nombre de bits de sortie a generer.

    Returns:
        Tableau uint8 de forme (2^reg_len, n_bits).
    """
    n_states = 1 << reg_len
    mask = np.int64((1 << reg_len) - 1)
    msb = reg_len - 1

    states = np.arange(n_states, dtype=np.int64)
    outputs = np.empty((n_states, n_bits), dtype=np.uint8)

    for i in range(n_bits):
        outputs[:, i] = (states >> msb) & 1
        fb = np.zeros(n_states, dtype=np.int64)
        for t in taps:
            fb ^= (states >> t) & 1
        states = ((states >> 1) | (fb << msb)) & mask

    return outputs


def _best_correlation(
    outputs: NDArray[np.uint8],
    keystream: UInt8Array,
) -> tuple[int, float]:
    """Retourne l'index et la correlation normalisee maximale contre le keystream.

    Args:
        outputs:   (n_states, n_bits) tableau de sorties LFSR.
        keystream: bits de cle connus (longueur n_bits).

    Returns:
        (best_state_idx, correlation) avec correlation dans [-1, +1].
    """
    n_bits = keystream.shape[0]
    ks_signed = (2 * keystream.astype(np.int8) - 1).astype(np.float32)
    out_signed = (2 * outputs.astype(np.int8) - 1).astype(np.float32)
    # Produit scalaire de chaque ligne avec le keystream signe
    correlations: FloatArray = (out_signed @ ks_signed) / n_bits
    best_idx = int(np.argmax(correlations))
    return best_idx, float(correlations[best_idx])


def brute_force_r1(keystream: UInt8Array) -> tuple[int, float]:
    """Recherche exhaustive de l'etat initial de R1 (2^19 = 524 288 candidats).

    Args:
        keystream: flux de cle connu (au moins 20 bits recommande).

    Returns:
        (etat_r1, correlation) - etat initial de R1 produisant la plus forte
        correlation avec le keystream en mode autonome.
    """
    if len(keystream) < 1:
        raise ValueError("keystream doit avoir au moins 1 bit")
    outputs = _all_lfsr_outputs(_R1_LEN, _R1_TAPS, len(keystream))
    return _best_correlation(outputs, keystream)


def brute_force_r2(keystream: UInt8Array) -> tuple[int, float]:
    """Recherche exhaustive de l'etat initial de R2 (2^22 = 4 194 304 candidats).

    Note : necessite ~320 Mo de RAM. Sur machine standard, ~5-15s.
    """
    if len(keystream) < 1:
        raise ValueError("keystream doit avoir au moins 1 bit")
    outputs = _all_lfsr_outputs(_R2_LEN, _R2_TAPS, len(keystream))
    return _best_correlation(outputs, keystream)


def brute_force_r3(keystream: UInt8Array) -> tuple[int, float]:
    """Recherche exhaustive de l'etat initial de R3 (2^23 = 8 388 608 candidats).

    Note : necessite ~640 Mo de RAM. Sur machine standard, ~10-30s.
    """
    if len(keystream) < 1:
        raise ValueError("keystream doit avoir au moins 1 bit")
    outputs = _all_lfsr_outputs(_R3_LEN, _R3_TAPS, len(keystream))
    return _best_correlation(outputs, keystream)


# ---------------------------------------------------------------------------
# Etape 3 : verification de l'etat retrouve
# ---------------------------------------------------------------------------

def verify_state(
    r1: int, r2: int, r3: int, keystream: UInt8Array
) -> tuple[float, UInt8Array]:
    """Simule le chiffrement depuis l'etat (r1, r2, r3) avec clocking majoritaire
    et compare la sortie au flux de cle connu.

    Args:
        r1, r2, r3: etats initiaux des trois registres.
        keystream:  flux de cle attendu.

    Returns:
        (taux_correspondance, bits_generes) : taux dans [0, 1] et flux de cle genere.
    """
    state = _A5State(r1=r1, r2=r2, r3=r3)
    n = len(keystream)
    generated = np.empty(n, dtype=np.uint8)
    for i in range(n):
        generated[i] = _run_clock(state)
    match_rate = float(np.mean(generated == keystream))
    return match_rate, generated


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------

@dataclass
class CryptanalysisResult:
    """Resultat de la cryptanalyse A5/GMR-1."""

    r1_state: int
    r2_state: int
    r3_state: int
    r1_corr: float    # correlation R1 free-running vs keystream
    r2_corr: float
    r3_corr: float
    verification_rate: float  # taux de bits corrects avec clocking majoritaire
    keystream_recovered: UInt8Array  # flux de cle reconstruit


def attack_known_plaintext(
    plaintext: UInt8Array,
    ciphertext: UInt8Array,
    search_r2_r3: bool = False,
) -> CryptanalysisResult:
    """Attaque A5/GMR-1 a texte clair connu en trois etapes.

    1. Recupere le flux de cle (trivial : XOR).
    2. Retrouve l'etat de R1 (2^19 recherche exhaustive vectorisee).
    3. Si search_r2_r3=True, retrouve R2 (2^22) et R3 (2^23) - prend plus de temps.
    4. Verifie l'etat retrouve par simulation complete.

    Args:
        plaintext:     bits clairs (0/1).
        ciphertext:    bits chiffres correspondants.
        search_r2_r3:  si True, effectue aussi la recherche de R2 et R3 ;
                       si False, seul R1 est retrouve (R2=R3=0 dans le resultat).

    Returns:
        CryptanalysisResult avec les etats retrouves et le taux de verification.
    """
    keystream = recover_keystream(plaintext, ciphertext)

    r1_state, r1_corr = brute_force_r1(keystream)

    r2_state, r2_corr = (0, 0.0)
    r3_state, r3_corr = (0, 0.0)

    if search_r2_r3:
        r2_state, r2_corr = brute_force_r2(keystream)
        r3_state, r3_corr = brute_force_r3(keystream)

    verification_rate, ks_reconstructed = verify_state(
        r1_state, r2_state, r3_state, keystream
    )

    return CryptanalysisResult(
        r1_state=r1_state,
        r2_state=r2_state,
        r3_state=r3_state,
        r1_corr=r1_corr,
        r2_corr=r2_corr,
        r3_corr=r3_corr,
        verification_rate=verification_rate,
        keystream_recovered=ks_reconstructed,
    )
