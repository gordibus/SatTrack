"""Tests unitaires du controleur de rotateur (F9).

La logique pure (``az_el_clamp``, ``track_pass``) est testee sans mock : le
backend factice est une vraie implementation en memoire qui enregistre les
commandes recues, et la trajectoire d'interop provient d'un appel reel a
``compute_trajectory`` (F2).
"""

from __future__ import annotations

import pytest
from skyfield.api import load

from satrx.antenna.rotator import (
    AzElPosition,
    RotatorController,
    az_el_clamp,
)
from satrx.tracking.passes import TrajectoryPoint, compute_trajectory, find_passes
from satrx.tracking.station import GroundStation
from satrx.tracking.tle import load_satellite

# TLE ISS reutilise depuis tests/tracking/test_trajectory.py (ephemeride reelle).
ISS_LINE1 = "1 25544U 98067A   24079.54791667  .00016717  00000-0  30289-3 0  9993"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560686447896"
PARIS = GroundStation(name="Paris", latitude_deg=48.8566, longitude_deg=2.3522, elevation_m=35.0)


class FacticeBackend:
    """Backend en memoire satisfaisant le protocole ``CommandBackend``.

    Enregistre chaque commande envoyee ; repond ``OK`` sauf a ``GET`` ou il
    renvoie une position figee. Aucune I/O, aucun mock.
    """

    def __init__(self, get_response: str = "AZ12.0 EL34.0") -> None:
        self.commands: list[str] = []
        self._get_response = get_response

    def send_command(self, cmd: str) -> str:
        self.commands.append(cmd)
        if cmd == "GET":
            return self._get_response
        return "OK"

    @property
    def is_connected(self) -> bool:
        return True


class TestAzElClamp:

    def test_nominal_dans_plage(self) -> None:
        # az=127.4, el=42.6 sont dans la plage servo -> renvoyes sans modification.
        assert az_el_clamp(127.4, 42.6) == AzElPosition(az_deg=127.4, el_deg=42.6)

    def test_flip_az_superieur_175(self) -> None:
        # az=200 hors plage servo [0,180] -> flip azimutal az-180 = 20.
        # el conserve (le servo EL 0-90 interdit le flip over-the-top 180-el).
        result = az_el_clamp(200.0, 30.0)
        assert result == AzElPosition(az_deg=20.0, el_deg=30.0)

    def test_azimut_normalise_modulo_360(self) -> None:
        # az=365 -> 5 (dans la plage servo, pas de flip).
        assert az_el_clamp(365.0, 10.0) == AzElPosition(az_deg=5.0, el_deg=10.0)

    def test_elevation_hors_plage_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            az_el_clamp(90.0, -5.0)
        with pytest.raises(ValueError):
            az_el_clamp(90.0, 120.0)


class TestRotatorControllerCommands:

    def test_goto_envoie_commande_clampee(self) -> None:
        backend = FacticeBackend()
        RotatorController(backend).goto(127.4, 42.6)
        assert backend.commands == ["AZ127.4 EL42.6"]

    def test_get_position_parse_reponse(self) -> None:
        backend = FacticeBackend(get_response="AZ127.4 EL42.6")
        pos = RotatorController(backend).get_position()
        assert pos == AzElPosition(az_deg=127.4, el_deg=42.6)

    def test_home_park_stop(self) -> None:
        backend = FacticeBackend()
        controller = RotatorController(backend)
        controller.home()
        controller.park()
        controller.stop()
        assert backend.commands == ["HOME", "PARK", "STOP"]


class TestRotatorControllerTrackPass:

    def test_interop_trajectory_point_f2(self) -> None:
        # track_pass consomme directement la sortie de compute_trajectory (F2),
        # sans conversion manuelle.
        ts = load.timescale()
        satellite = load_satellite("ISS (ZARYA)", ISS_LINE1, ISS_LINE2)
        sat_pass = find_passes(
            satellite, PARIS, ts.utc(2024, 3, 20), ts.utc(2024, 3, 21), min_elevation_deg=10.0
        )[0]
        duration_s = (sat_pass.set_time.tt - sat_pass.rise_time.tt) * 86400.0
        points = compute_trajectory(satellite, PARIS, sat_pass.rise_time, duration_s, n_samples=60)

        waited: list[float] = []
        backend = FacticeBackend()
        controller = RotatorController(backend, sleep_fn=waited.append)
        controller.track_pass(points, min_elevation_deg=5.0)

        expected_goto = sum(1 for p in points if p.elevation_deg >= 5.0)
        goto_cmds = [c for c in backend.commands if c.startswith("AZ")]
        assert len(goto_cmds) == expected_goto
        assert expected_goto > 0  # le passage culmine bien au-dessus de 5 degres
        assert backend.commands[-1] == "PARK"  # arret propre en fin de suivi
        assert all(w >= 0.0 for w in waited)

    def test_ignore_points_sous_elevation_min(self) -> None:
        # Trajectoire synthetique : seuls les points el >= 5 doivent etre envoyes.
        points = [
            TrajectoryPoint(seconds_from_start=0.0, elevation_deg=3.0, azimuth_deg=100.0),
            TrajectoryPoint(seconds_from_start=1.0, elevation_deg=10.0, azimuth_deg=110.0),
            TrajectoryPoint(seconds_from_start=2.0, elevation_deg=4.9, azimuth_deg=120.0),
            TrajectoryPoint(seconds_from_start=3.0, elevation_deg=20.0, azimuth_deg=130.0),
        ]
        backend = FacticeBackend()
        controller = RotatorController(backend, sleep_fn=lambda _s: None)
        controller.track_pass(points, min_elevation_deg=5.0)

        goto_cmds = [c for c in backend.commands if c.startswith("AZ")]
        assert goto_cmds == ["AZ110.0 EL10.0", "AZ130.0 EL20.0"]
        assert backend.commands[-1] == "PARK"

    def test_stop_interrompt_le_suivi_et_park(self) -> None:
        # stop() en cours de suivi coupe l'envoi des points restants mais park.
        points = [
            TrajectoryPoint(seconds_from_start=float(i), elevation_deg=30.0, azimuth_deg=100.0)
            for i in range(5)
        ]
        backend = FacticeBackend()
        controller = RotatorController(backend, sleep_fn=lambda _s: None)

        # Stoppe des le premier point en detournant le backend.
        original_send = backend.send_command

        def send_then_stop(cmd: str) -> str:
            result = original_send(cmd)
            if cmd.startswith("AZ"):
                controller.stop()
            return result

        backend.send_command = send_then_stop  # type: ignore[method-assign]
        controller.track_pass(points, min_elevation_deg=5.0)

        goto_cmds = [c for c in backend.commands if c.startswith("AZ")]
        assert len(goto_cmds) == 1  # un seul point envoye avant l'arret
        assert backend.commands[-1] == "PARK"
        assert "STOP" in backend.commands
