"""Controle haut niveau du rotateur d'antenne 2 axes (F9).

Le rotateur physique est un montage AZ/EL a servos MG996R standard piloté par un
Arduino Nano (cf. ``docs/f9_rotateur/``) :

- servo AZ : plage utile mecanique 0-180 degres (servo standard, PAS de rotation
  continue) ;
- servo EL : plage utile 0-90 degres.

Ce module consomme directement les ``TrajectoryPoint`` produits par F2
(``satrx.tracking.passes.compute_trajectory``) et n'effectue aucune I/O serie
lui-meme : il delegue a un backend (``SerialBackend`` en production, un backend
factice en test) via le protocole :class:`CommandBackend`.

Note materiel (limite documentee) : sur un montage AZ 0-180 / EL 0-90, un vrai
"flip" over-the-top (pointer l'azimut oppose az-180 et basculer l'elevation a
180-el) est physiquement impossible car le servo EL ne depasse pas 90 degres.
:func:`az_el_clamp` ramene donc l'azimut dans la plage servo et conserve
l'elevation ; les cibles de l'hemisphere arriere (azimut vrai 180-360) ne sont
pas rigoureusement atteignables avec ce materiel - limitation a lever cote
mecanique (servo EL 0-180 ou az a rotation continue), pas cote logiciel.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol

from satrx.tracking.passes import TrajectoryPoint

# Seuil au-dela duquel l'azimut sort de la plage servo sure et declenche le flip.
_AZ_FLIP_THRESHOLD_DEG = 175.0
_AZ_SERVO_MAX_DEG = 180.0
_EL_SERVO_MAX_DEG = 90.0


@dataclass(frozen=True)
class AzElPosition:
    """Consigne ou position mesuree du rotateur, dans la plage servo physique."""

    az_deg: float  # 0.0 .. 180.0 (limite servo standard)
    el_deg: float  # 0.0 .. 90.0


class RotatorTimeoutError(Exception):
    """Le rotateur n'a pas repondu dans le delai imparti (timeout serie)."""


class CommandBackend(Protocol):
    """Contrat minimal attendu d'un backend par :class:`RotatorController`.

    ``SerialBackend`` le satisfait structurellement ; un backend factice en
    memoire aussi, ce qui permet de tester ``track_pass`` sans materiel.
    """

    def send_command(self, cmd: str) -> str: ...

    @property
    def is_connected(self) -> bool: ...


def az_el_clamp(az: float, el: float) -> AzElPosition:
    """Contraint (az, el) dans la plage servo physique du rotateur.

    - ``el`` doit etre dans [0, 90] : hors de cette plage -> :class:`ValueError`
      (le servo EL ne peut pas y aller ; on ne clippe pas silencieusement une
      elevation aberrante).
    - ``az`` est normalise modulo 360, puis, au-dela de
      ``_AZ_FLIP_THRESHOLD_DEG`` (175), ramene dans la plage servo [0, 180] par
      un decalage de 180 degres (flip azimutal). L'elevation est conservee :
      voir la note materiel du module (le flip over-the-top ``el = 180 - el``
      exigerait un servo EL 0-180, indisponible ici).

    >>> az_el_clamp(127.4, 42.6)
    AzElPosition(az_deg=127.4, el_deg=42.6)
    >>> az_el_clamp(200.0, 30.0)
    AzElPosition(az_deg=20.0, el_deg=30.0)
    """
    if not 0.0 <= el <= _EL_SERVO_MAX_DEG:
        raise ValueError(
            f"Elevation hors plage servo [0, {_EL_SERVO_MAX_DEG}] : {el}"
        )

    az_norm = az % 360.0
    if az_norm > _AZ_FLIP_THRESHOLD_DEG:
        az_norm -= 180.0
    az_clamped = min(max(az_norm, 0.0), _AZ_SERVO_MAX_DEG)
    return AzElPosition(az_deg=az_clamped, el_deg=el)


class RotatorController:
    """Controleur haut niveau : consomme des ``TrajectoryPoint`` (F2)."""

    def __init__(
        self,
        backend: CommandBackend,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._backend = backend
        # Injectable pour rendre track_pass testable sans attente reelle.
        self._sleep = sleep_fn
        self._stop_requested = False

    def goto(self, az: float, el: float) -> None:
        """Envoie une consigne de deplacement, apres clamp servo.

        Leve :class:`RotatorTimeoutError` si le backend ne repond pas.
        """
        # Import local pour eviter tout cycle d'import serial_backend <-> rotator.
        from satrx.antenna.serial_backend import format_goto_command

        target = az_el_clamp(az, el)
        self._backend.send_command(
            format_goto_command(target.az_deg, target.el_deg)
        )

    def home(self) -> None:
        self._backend.send_command("HOME")

    def park(self) -> None:
        self._backend.send_command("PARK")

    def stop(self) -> None:
        """Arret d'urgence : coupe le suivi en cours et commande STOP."""
        self._stop_requested = True
        self._backend.send_command("STOP")

    def get_position(self) -> AzElPosition:
        """Interroge le rotateur (``GET``) et retourne la position mesuree."""
        from satrx.antenna.serial_backend import parse_position_response

        return parse_position_response(self._backend.send_command("GET"))

    def track_pass(
        self,
        points: list[TrajectoryPoint],
        min_elevation_deg: float = 5.0,
    ) -> None:
        """Suit un passage satellite point par point.

        - Ignore les points sous ``min_elevation_deg`` (satellite trop bas /
          sous l'horizon utile).
        - Applique :func:`az_el_clamp` sur chaque point avant envoi.
        - Attend le delai relatif (``seconds_from_start``) entre deux points
          effectivement suivis.
        - Se termine proprement par ``park()``, y compris si :meth:`stop` est
          appele en cours de suivi.
        """
        self._stop_requested = False
        last_sent_s: float | None = None
        try:
            for point in points:
                if self._stop_requested:
                    break
                if point.elevation_deg < min_elevation_deg:
                    continue
                if last_sent_s is not None:
                    wait_s = point.seconds_from_start - last_sent_s
                    if wait_s > 0.0:
                        self._sleep(wait_s)
                if self._stop_requested:
                    break
                self.goto(point.azimuth_deg, point.elevation_deg)
                last_sent_s = point.seconds_from_start
        finally:
            self.park()
