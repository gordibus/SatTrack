"""Analyse de patterns de fraude sur sessions GMR-1 simulees (B8-LAB-FRAUD).

Scenarios implementes :
  1. Clonage d'identifiant (IMSI cloning) : deux sessions simultanees avec le
     meme IMSI dans des slots differents.
  2. Replay d'identifiant de session (TMSI/sequence) : numero de sequence
     non monotone, indiquant la reutilisation d'un ancien contexte de session.
  3. Ecart de facturation (usage sans facturation) : gap anormal entre deux
     evenements de facturation consecutifs pour le meme abonne.

Le module fournit aussi un generateur de sessions synthetiques reproduisant
ces patterns pour permettre la validation des detecteurs.

Note sur le niveau de preuve : ces detecteurs sont valides sur des sessions
SIMULEES dans l'environnement lab isole. Les seuils et la distribution des
parametres (gap, fenetre de detection) sont calibres sur la simulation et
devront etre ajustes sur des donnees reelles de production.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from satrx.security.gmr1.constants import GMR1_FRAME_SLOTS


# ---------------------------------------------------------------------------
# Structures de donnees
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    """Enregistrement de session GMR-1 (une transaction par burst actif)."""

    frame_num: int      # numero de trame TDMA
    slot: int           # slot TDMA [0, GMR1_FRAME_SLOTS[
    imsi_hash: int      # SHA-256[:32 bits] de l'IMSI (identifiant hache, jamais en clair)
    tmsi: int           # identifiant temporaire alloue par le reseau
    seq_num: int        # numero de sequence monotone par session
    billed: bool        # True si un evenement de facturation a ete genere


@dataclass
class FraudAlert:
    """Alerte de fraude detectee."""

    alert_type: str          # "clone" | "replay" | "billing_gap"
    imsi_hash: int
    severity: str            # "HIGH" | "MEDIUM" | "LOW"
    frame_refs: list[int]    # numeros de trame impliques
    details: str             # description technique de l'anomalie


# ---------------------------------------------------------------------------
# Generateur de sessions synthetiques
# ---------------------------------------------------------------------------

def _hash_imsi(imsi_str: str) -> int:
    """Hache un IMSI en 32 bits (pour le lab - ne jamais stocker l'IMSI en clair)."""
    return int(hashlib.sha256(imsi_str.encode()).hexdigest()[:8], 16)


def simulate_normal_sessions(
    n_subscribers: int,
    n_frames: int,
    rng: np.random.Generator | None = None,
) -> list[SessionRecord]:
    """Genere n_frames trames de sessions normales pour n_subscribers abonnes.

    Chaque abonne occupe un slot fixe par trame. Les numeros de sequence
    sont strictement croissants. Tous les evenements sont factures.

    Args:
        n_subscribers: nombre d'abonnes simules (max GMR1_FRAME_SLOTS).
        n_frames:      nombre de trames a simuler.
        rng:           generateur aleatoire (reproductible si fourni).

    Returns:
        Liste de SessionRecord triee par (frame_num, slot).
    """
    if not 1 <= n_subscribers <= GMR1_FRAME_SLOTS:
        raise ValueError(
            f"n_subscribers doit etre dans [1, {GMR1_FRAME_SLOTS}], recu {n_subscribers}"
        )
    if n_frames < 1:
        raise ValueError("n_frames doit etre >= 1")

    _rng = rng if rng is not None else np.random.default_rng(0)
    records: list[SessionRecord] = []

    imsi_hashes = [_hash_imsi(f"310260{i:09d}") for i in range(n_subscribers)]
    tmsis = _rng.integers(0x1000, 0xFFFF, size=n_subscribers, dtype=np.int32).tolist()
    seq_nums = [0] * n_subscribers

    for frame in range(n_frames):
        for sub_idx in range(n_subscribers):
            seq_nums[sub_idx] += 1
            records.append(SessionRecord(
                frame_num=frame,
                slot=sub_idx,
                imsi_hash=imsi_hashes[sub_idx],
                tmsi=tmsis[sub_idx],
                seq_num=seq_nums[sub_idx],
                billed=True,
            ))

    return records


def inject_clone_attack(
    records: list[SessionRecord],
    target_imsi_hash: int,
    start_frame: int,
    clone_slot: int,
    n_frames: int = 5,
) -> list[SessionRecord]:
    """Injecte un scenario de clonage d'identifiant.

    Ajoute des enregistrements avec le meme IMSI hash dans un slot different
    de celui de l'abonne legitime, simulant l'utilisation simultanee de deux
    terminaux avec le meme identifiant.

    Args:
        records:          enregistrements de session existants.
        target_imsi_hash: IMSI hash de l'abonne cible.
        start_frame:      premiere trame du clonage.
        clone_slot:       slot utilise par le clone (different du slot legitime).
        n_frames:         duree du clonage en nombre de trames.

    Returns:
        Nouveaux enregistrements avec le clonage injecte.
    """
    injected = list(records)
    seq = 9000  # sequence haute pour distinguer le clone du trafic legitime
    for frame in range(start_frame, start_frame + n_frames):
        seq += 1
        injected.append(SessionRecord(
            frame_num=frame,
            slot=clone_slot,
            imsi_hash=target_imsi_hash,
            tmsi=0xDEAD,  # TMSI different du TMSI legitime - indicateur de clonage
            seq_num=seq,
            billed=False,  # le clone ne passe pas par la facturation
        ))
    return sorted(injected, key=lambda r: (r.frame_num, r.slot))


def inject_replay_attack(
    records: list[SessionRecord],
    target_imsi_hash: int,
    replay_at_frame: int,
) -> list[SessionRecord]:
    """Injecte un replay d'ancien numero de sequence.

    Remplace le numero de sequence d'une trame par une valeur
    inferieure au numero precedent du meme abonne, simulant la reutilisation
    d'un contexte de session capture et reemis.

    Args:
        records:          enregistrements de session existants.
        target_imsi_hash: IMSI hash de l'abonne cible.
        replay_at_frame:  trame ou le replay est injecte.

    Returns:
        Copie des enregistrements avec le replay injecte.
    """
    injected = list(records)
    for i, r in enumerate(injected):
        if r.imsi_hash == target_imsi_hash and r.frame_num == replay_at_frame:
            injected[i] = SessionRecord(
                frame_num=r.frame_num,
                slot=r.slot,
                imsi_hash=r.imsi_hash,
                tmsi=r.tmsi,
                seq_num=1,   # retour en arriere : valeur tres basse = replay detectable
                billed=r.billed,
            )
            break
    return injected


def inject_billing_gap(
    records: list[SessionRecord],
    target_imsi_hash: int,
    gap_start_frame: int,
    gap_size: int,
) -> list[SessionRecord]:
    """Supprime les evenements de facturation sur une plage de trames.

    Simule un usage sans facturation : les sessions existent dans le flux
    radio (enregistrements presents) mais l'evenement de facturation est absent.

    Args:
        records:          enregistrements de session existants.
        target_imsi_hash: IMSI hash de l'abonne cible.
        gap_start_frame:  premiere trame sans facturation.
        gap_size:         nombre de trames sans facturation.

    Returns:
        Copie des enregistrements avec les facturations supprimees.
    """
    injected = []
    for r in records:
        if (
            r.imsi_hash == target_imsi_hash
            and gap_start_frame <= r.frame_num < gap_start_frame + gap_size
        ):
            injected.append(SessionRecord(
                frame_num=r.frame_num,
                slot=r.slot,
                imsi_hash=r.imsi_hash,
                tmsi=r.tmsi,
                seq_num=r.seq_num,
                billed=False,  # evenement de facturation absent
            ))
        else:
            injected.append(r)
    return injected


# ---------------------------------------------------------------------------
# Detecteurs
# ---------------------------------------------------------------------------

def detect_simultaneous_sessions(
    records: list[SessionRecord],
    window_frames: int = 1,
) -> list[FraudAlert]:
    """Detecte les sessions simultanees avec le meme IMSI hash (clonage).

    Un meme IMSI dans deux slots differents dans une fenetre de window_frames
    trames consecutive est considere comme un clone.

    Args:
        records:       enregistrements de session.
        window_frames: largeur de la fenetre de detection en trames.

    Returns:
        Liste d'alertes de type "clone".
    """
    from collections import defaultdict

    alerts: list[FraudAlert] = []
    # Grouper par (imsi_hash, fenetre de trame)
    window_sessions: dict[tuple[int, int], set[int]] = defaultdict(set)
    window_frames_map: dict[tuple[int, int], list[int]] = defaultdict(list)

    for r in records:
        key = (r.imsi_hash, r.frame_num // window_frames)
        window_sessions[key].add(r.slot)
        window_frames_map[key].append(r.frame_num)

    for (imsi_hash, window_idx), slots in window_sessions.items():
        if len(slots) > 1:
            frame_refs = window_frames_map[(imsi_hash, window_idx)]
            alerts.append(FraudAlert(
                alert_type="clone",
                imsi_hash=imsi_hash,
                severity="HIGH",
                frame_refs=sorted(set(frame_refs)),
                details=(
                    f"IMSI hash 0x{imsi_hash:08X} detecte dans {len(slots)} slots "
                    f"differents {sorted(slots)} dans la fenetre de trame {window_idx} "
                    f"(window={window_frames} trames)"
                ),
            ))

    return alerts


def detect_sequence_replay(
    records: list[SessionRecord],
) -> list[FraudAlert]:
    """Detecte les regressions de numero de sequence (replay).

    Pour chaque abonne, les numeros de sequence doivent etre strictement
    croissants. Une valeur decroissante ou egale a la precedente indique
    un replay ou une reutilisation de contexte de session.

    Args:
        records: enregistrements de session tries par frame_num.

    Returns:
        Liste d'alertes de type "replay".
    """
    alerts: list[FraudAlert] = []
    last_seq: dict[int, tuple[int, int]] = {}  # imsi_hash → (seq_num, frame_num)

    for r in sorted(records, key=lambda x: x.frame_num):
        if r.imsi_hash in last_seq:
            prev_seq, prev_frame = last_seq[r.imsi_hash]
            if r.seq_num <= prev_seq:
                alerts.append(FraudAlert(
                    alert_type="replay",
                    imsi_hash=r.imsi_hash,
                    severity="HIGH",
                    frame_refs=[prev_frame, r.frame_num],
                    details=(
                        f"IMSI hash 0x{r.imsi_hash:08X} : sequence {prev_seq} "
                        f"(trame {prev_frame}) → {r.seq_num} (trame {r.frame_num}) "
                        f"- regression de {prev_seq - r.seq_num} (replay probable)"
                    ),
                ))
        last_seq[r.imsi_hash] = (r.seq_num, r.frame_num)

    return alerts


def detect_billing_gaps(
    records: list[SessionRecord],
    max_unbilled_frames: int = 3,
) -> list[FraudAlert]:
    """Detecte les plages de sessions sans evenement de facturation.

    Un abonne dont les sessions ne sont pas facturees sur plus de
    max_unbilled_frames trames consecutives est signale.

    Args:
        records:              enregistrements de session.
        max_unbilled_frames:  seuil (inclus) de trames non facturees avant alerte.

    Returns:
        Liste d'alertes de type "billing_gap".
    """
    alerts: list[FraudAlert] = []
    # Grouper les runs de sessions non facturees par abonne
    from itertools import groupby

    by_imsi: dict[int, list[SessionRecord]] = {}
    for r in sorted(records, key=lambda x: (x.imsi_hash, x.frame_num)):
        by_imsi.setdefault(r.imsi_hash, []).append(r)

    for imsi_hash, sub_records in by_imsi.items():
        unbilled_run: list[int] = []
        for r in sub_records:
            if not r.billed:
                unbilled_run.append(r.frame_num)
            else:
                if len(set(unbilled_run)) > max_unbilled_frames:
                    alerts.append(FraudAlert(
                        alert_type="billing_gap",
                        imsi_hash=imsi_hash,
                        severity="MEDIUM",
                        frame_refs=sorted(set(unbilled_run)),
                        details=(
                            f"IMSI hash 0x{imsi_hash:08X} : {len(set(unbilled_run))} "
                            f"trames consecutives sans facturation "
                            f"(seuil={max_unbilled_frames})"
                        ),
                    ))
                unbilled_run = []
        # Verifier le run final
        if len(set(unbilled_run)) > max_unbilled_frames:
            alerts.append(FraudAlert(
                alert_type="billing_gap",
                imsi_hash=imsi_hash,
                severity="MEDIUM",
                frame_refs=sorted(set(unbilled_run)),
                details=(
                    f"IMSI hash 0x{imsi_hash:08X} : {len(set(unbilled_run))} "
                    f"trames consecutives sans facturation (seuil={max_unbilled_frames})"
                ),
            ))

    return alerts


def analyze_session_log(
    records: list[SessionRecord],
    window_frames: int = 1,
    max_unbilled_frames: int = 3,
) -> list[FraudAlert]:
    """Pipeline complet : applique les trois detecteurs et retourne toutes les alertes.

    Args:
        records:              enregistrements de session.
        window_frames:        fenetre de detection de clonage (en trames).
        max_unbilled_frames:  seuil de facturation manquante.

    Returns:
        Liste d'alertes fusionnee, triee par severite (HIGH en premier).
    """
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    alerts = (
        detect_simultaneous_sessions(records, window_frames)
        + detect_sequence_replay(records)
        + detect_billing_gaps(records, max_unbilled_frames)
    )
    return sorted(alerts, key=lambda a: severity_order.get(a.severity, 9))
