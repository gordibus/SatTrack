from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from satrx.decode.ccsds import CcsdsPacket

# Heuristique classique d'analyse forensique : un flux chiffre ou compresse a une entropie
# de Shannon proche de 8 bits/octet (quasi-uniforme) ; un flux clair/structure (texte, en-tetes,
# telemetrie peu variee) a une entropie nettement plus basse. Ce n'est pas une preuve formelle
# (des donnees compressees non chiffrees ont aussi une entropie elevee), mais un premier
# indicateur standard et largement utilise en analyse de securite.
HIGH_ENTROPY_THRESHOLD = 7.5
LOW_ENTROPY_THRESHOLD = 6.0


def shannon_entropy(data: bytes) -> float:
    if not data:
        raise ValueError("data ne doit pas etre vide")

    counts = Counter(data)
    length = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def classify_payload(data: bytes) -> str:
    entropy = shannon_entropy(data)
    if entropy >= HIGH_ENTROPY_THRESHOLD:
        return "probablement chiffre ou compresse"
    if entropy <= LOW_ENTROPY_THRESHOLD:
        return "probablement clair / structure"
    return "ambigu"


@dataclass(frozen=True)
class ApidEntropyReport:
    apid: int
    packet_count: int
    total_bytes: int
    mean_entropy: float
    classification: str


def analyze_packets_by_apid(packets: list[CcsdsPacket]) -> list[ApidEntropyReport]:
    if not packets:
        raise ValueError("packets ne doit pas etre vide")

    by_apid: dict[int, list[CcsdsPacket]] = {}
    for packet in packets:
        by_apid.setdefault(packet.header.apid, []).append(packet)

    reports = []
    for apid, apid_packets in sorted(by_apid.items()):
        non_empty = [p.data for p in apid_packets if p.data]
        if not non_empty:
            continue
        entropies = [shannon_entropy(data) for data in non_empty]
        mean_entropy = sum(entropies) / len(entropies)
        reports.append(
            ApidEntropyReport(
                apid=apid,
                packet_count=len(apid_packets),
                total_bytes=sum(len(p.data) for p in apid_packets),
                mean_entropy=mean_entropy,
                classification=classify_payload(b"".join(non_empty)),
            )
        )
    return reports
