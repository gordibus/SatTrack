from __future__ import annotations

from dataclasses import dataclass

# Structure de "temps de bord" (onboard time) confirmee dans le decodeur LRPT open source
# artlav/meteor_decoder (fonction parse_70, fichier met_packet.pas) : 4 octets consecutifs
# heure/minute/seconde/dixaine-de-ms (x4 pour obtenir des ms). Recherche du 16/08/2026.
# CONFLIT RESOLU : une premiere source (meteorm2.particlesector.com) associait l'APID 70 a
# un canal image IR thermique, en contradiction avec parse_70 (temps de bord). Une
# troisieme source independante (recherche web generaliste : "Meteor M-N2-2 has telemetry
# on APID70, which contains information from the satellite including position data")
# confirme que l'APID 70 est bien de la telemetrie, pas un canal image - la premiere source
# etait erronee, corrigee dans `image/compose.py::METEOR_LRPT_APID_CHANNELS`. Cette
# fonction reste independante de l'APID (offset fourni par l'appelant) par simplicite.


@dataclass(frozen=True)
class OnboardTime:
    hours: int
    minutes: int
    seconds: int
    milliseconds: int

    def to_milliseconds_of_day(self) -> int:
        return (self.hours * 3600 + self.minutes * 60 + self.seconds) * 1000 + self.milliseconds


def parse_onboard_time(data: bytes, offset: int = 0) -> OnboardTime:
    if offset < 0:
        raise ValueError(f"offset doit etre >= 0, recu {offset}")
    if len(data) < offset + 4:
        raise ValueError(
            f"data trop court : {len(data)} octets fournis, {offset + 4} requis a partir de l'offset {offset}"
        )

    hours, minutes, seconds, ms_raw = data[offset : offset + 4]

    if not 0 <= hours < 24:
        raise ValueError(f"heures hors limites : {hours}")
    if not 0 <= minutes < 60:
        raise ValueError(f"minutes hors limites : {minutes}")
    if not 0 <= seconds < 60:
        raise ValueError(f"secondes hors limites : {seconds}")

    return OnboardTime(hours=hours, minutes=minutes, seconds=seconds, milliseconds=ms_raw * 4)
