from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# CCSDS Unsegmented Time Code (CUC, CCSDS 301.0-B) : temps grossier (secondes depuis une
# epoque de mission) + temps fin (fraction de seconde). Le nombre d'octets de chaque partie
# et l'epoque elle-meme sont specifiques a la mission (ici Meteor-M, non confirmes) - valeurs
# par defaut (4 octets grossiers, 2 fins) parmi les plus courantes, a ajuster si besoin.


@dataclass(frozen=True)
class CucTime:
    coarse_seconds: int
    fine_fraction: float

    def to_datetime(self, epoch: datetime) -> datetime:
        return epoch + timedelta(seconds=self.coarse_seconds + self.fine_fraction)


def decode_cuc_time(data: bytes, coarse_bytes: int = 4, fine_bytes: int = 2) -> CucTime:
    if coarse_bytes <= 0:
        raise ValueError(f"coarse_bytes doit etre positif, recu {coarse_bytes}")
    if fine_bytes < 0:
        raise ValueError(f"fine_bytes doit etre >= 0, recu {fine_bytes}")

    total = coarse_bytes + fine_bytes
    if len(data) < total:
        raise ValueError(f"data trop court : {len(data)} octets fournis, {total} requis")

    coarse_seconds = int.from_bytes(data[:coarse_bytes], byteorder="big")
    if fine_bytes > 0:
        fine_raw = int.from_bytes(data[coarse_bytes:total], byteorder="big")
        fine_fraction = fine_raw / (1 << (fine_bytes * 8))
    else:
        fine_fraction = 0.0

    return CucTime(coarse_seconds=coarse_seconds, fine_fraction=fine_fraction)
