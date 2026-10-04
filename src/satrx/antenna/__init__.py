"""F9 - Pointage d'antenne assiste/motorise (rotateur 2 axes AZ/EL).

Exporte l'interface publique du module rotateur : le controleur haut niveau,
les types de position/erreur et la fonction de contrainte servo.
"""

from satrx.antenna.rotator import (
    AzElPosition,
    RotatorController,
    RotatorTimeoutError,
    az_el_clamp,
)
from satrx.antenna.exos2_backend import (
    ExosIIBackend,
    azel_to_radec,
    radec_to_azel,
    build_goto_frame,
    build_stop_frame,
    build_park_frame,
    parse_position_frame,
)

__all__ = [
    "AzElPosition",
    "RotatorController",
    "RotatorTimeoutError",
    "az_el_clamp",
    "ExosIIBackend",
    "azel_to_radec",
    "radec_to_azel",
    "build_goto_frame",
    "build_stop_frame",
    "build_park_frame",
    "parse_position_frame",
]
