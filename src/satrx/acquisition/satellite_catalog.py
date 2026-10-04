from __future__ import annotations

from dataclasses import dataclass

# Catalogue des satellites connus avec leurs parametres RF.
#
# Convention d'offset LO :
#   - lo_offset_hz est negatif (-200 000 Hz) pour les satellites LRPT/APT VHF
#   - hackrf_center_hz = tx_freq_hz + lo_offset_hz
#   - Dans le spectre baseband le signal apparait a -lo_offset_hz = +200 kHz
#   - freq_offset_khz pour decode_lrpt.py = -lo_offset_hz / 1000 = 200.0
#
# Pourquoi -200 kHz ?
#   Le HackRF genere une fuite d'oscillateur local (spike DC) exactement a 0 Hz
#   dans le spectre baseband. Centrer le SDR pile sur la frequence satellite place
#   ce spike au milieu du signal LRPT (bande ~144 kHz). Decaler de -200 kHz eloigne
#   le signal du DC tout en le gardant dans la fenetre des 2.048 Msps.


@dataclass(frozen=True)
class SatelliteRFProfile:
    norad_id: int
    name: str
    tx_freq_hz: float
    lo_offset_hz: float
    modulation: str
    symbol_rate_bd: int
    description: str

    @property
    def hackrf_center_hz(self) -> float:
        """Frequence a commander au HackRF pour ce satellite (avant correction PPM)."""
        return self.tx_freq_hz + self.lo_offset_hz

    @property
    def freq_offset_khz(self) -> float:
        """Offset en kHz entre le centre HackRF et le signal (arg --freq-offset-khz)."""
        return -self.lo_offset_hz / 1000.0


# Satellites actifs connus (verifie octobre 2026)
# Sources : NOAA Space Weather / SatDump wiki / N2YO
CATALOG: list[SatelliteRFProfile] = [
    SatelliteRFProfile(
        norad_id=57166,
        name="METEOR-M2 3",
        tx_freq_hz=137_900_000.0,
        lo_offset_hz=-200_000.0,
        modulation="LRPT",
        symbol_rate_bd=72_000,
        description="Meteor-M2 3 (actif 2023+) - LRPT 72kBd QPSK 137.9 MHz",
    ),
    SatelliteRFProfile(
        norad_id=59051,
        name="METEOR-M2 4",
        tx_freq_hz=137_900_000.0,
        lo_offset_hz=-200_000.0,
        modulation="LRPT",
        symbol_rate_bd=72_000,
        description="Meteor-M2 4 (actif 2024+) - LRPT 72kBd QPSK 137.9 MHz",
    ),
    SatelliteRFProfile(
        norad_id=40069,
        name="METEOR-M2 2",
        tx_freq_hz=137_900_000.0,
        lo_offset_hz=-200_000.0,
        modulation="LRPT",
        symbol_rate_bd=72_000,
        description="Meteor-M2 2 (LRPT intermittent depuis impact 2019)",
    ),
    SatelliteRFProfile(
        norad_id=28654,
        name="NOAA 18",
        tx_freq_hz=137_912_500.0,
        lo_offset_hz=-212_500.0,
        modulation="APT",
        symbol_rate_bd=4_160,
        description="NOAA 18 - APT 137.9125 MHz (actif)",
    ),
    SatelliteRFProfile(
        norad_id=33591,
        name="NOAA 19",
        tx_freq_hz=137_100_000.0,
        lo_offset_hz=-200_000.0,
        modulation="APT",
        symbol_rate_bd=4_160,
        description="NOAA 19 - APT 137.1 MHz (actif)",
    ),
    SatelliteRFProfile(
        norad_id=25338,
        name="NOAA 15",
        tx_freq_hz=137_620_000.0,
        lo_offset_hz=-200_000.0,
        modulation="APT",
        symbol_rate_bd=4_160,
        description="NOAA 15 - APT 137.62 MHz (actif)",
    ),
    SatelliteRFProfile(
        norad_id=25544,
        name="ISS (ZARYA)",
        tx_freq_hz=145_800_000.0,
        lo_offset_hz=-200_000.0,
        modulation="SSTV",
        symbol_rate_bd=0,
        description="ISS - SSTV/voix 145.8 MHz (occasionnel)",
    ),
    SatelliteRFProfile(
        norad_id=0,
        name="IRIDIUM",
        tx_freq_hz=1_621_250_000.0,
        lo_offset_hz=-250_000.0,
        modulation="QPSK",
        symbol_rate_bd=25_000,
        description="Iridium burst 1621.25 MHz",
    ),
]

_BY_NORAD: dict[int, SatelliteRFProfile] = {p.norad_id: p for p in CATALOG}
_BY_NAME: dict[str, SatelliteRFProfile] = {p.name.upper(): p for p in CATALOG}


def lookup_by_norad(norad_id: int) -> SatelliteRFProfile | None:
    """Retourne le profil RF d'un satellite depuis son NORAD ID, ou None si inconnu."""
    return _BY_NORAD.get(norad_id)


def lookup_by_name(name: str) -> SatelliteRFProfile | None:
    """Retourne le profil RF depuis le nom du satellite (insensible a la casse).

    Essaie la correspondance exacte, puis la correspondance partielle.
    """
    upper = name.upper()
    if upper in _BY_NAME:
        return _BY_NAME[upper]
    for catalog_name, profile in _BY_NAME.items():
        if upper in catalog_name or catalog_name in upper:
            return profile
    return None


def hackrf_center_with_ppm(profile: SatelliteRFProfile, ppm: int) -> float:
    """Frequence a commander au HackRF en tenant compte du drift PPM.

    Le HackRF a un oscillateur qui derive de `ppm` parties par million par rapport
    a la frequence commandee. Pour que l'oscillateur local soit reellement a
    `profile.hackrf_center_hz`, il faut commander une frequence legerement plus basse
    (si ppm > 0 = oscillateur trop haut).

    Formule : freq_commandee = freq_desiree / (1 + ppm / 1_000_000)
    """
    if ppm == 0:
        return profile.hackrf_center_hz
    return profile.hackrf_center_hz / (1.0 + ppm / 1_000_000.0)
