"""Tests unitaires de la couche serie du rotateur (F9).

Seule la logique pure est testee ici sans materiel :
- ``format_goto_command`` (formatage de la trame de deplacement) ;
- ``parse_position_response`` (parsing de la reponse ``GET``).

Ce qui reste a couvrir par ``tests/integration/`` (Arduino Nano branche sur
``/dev/ttyUSB0``, non disponible en CI) :
- ``SerialBackend.connect`` / ``disconnect`` (ouverture reelle du port) ;
- ``SerialBackend.send_command`` : aller-retour reel PC <-> Arduino et
  declenchement effectif de ``RotatorTimeoutError`` sur silence materiel.
La logique de decision de ``send_command`` (echec si port ferme, timeout si
``readline`` vide) est deterministe et sera verifiee sur banc materiel.
"""

from __future__ import annotations

import pytest

from satrx.antenna.rotator import AzElPosition
from satrx.antenna.serial_backend import (
    format_goto_command,
    parse_position_response,
)


class TestFormatGotoCommand:

    def test_nominal_une_decimale(self) -> None:
        assert format_goto_command(127.4, 42.6) == "AZ127.4 EL42.6"

    def test_arrondi_a_une_decimale(self) -> None:
        # La resolution servo ne justifie pas plus d'une decimale : arrondi stable.
        assert format_goto_command(0.04, 89.96) == "AZ0.0 EL90.0"

    def test_interop_parse_reciproque(self) -> None:
        # La trame formatee doit etre relisible par le parseur (aller-retour).
        cmd = format_goto_command(12.3, 45.6)
        assert parse_position_response(cmd) == AzElPosition(az_deg=12.3, el_deg=45.6)


class TestParsePositionResponse:

    def test_nominal(self) -> None:
        assert parse_position_response("AZ127.4 EL42.6") == AzElPosition(
            az_deg=127.4, el_deg=42.6
        )

    def test_espaces_et_retour_ligne_tolerés(self) -> None:
        assert parse_position_response("  AZ12.0  EL34.0\r\n") == AzElPosition(
            az_deg=12.0, el_deg=34.0
        )

    def test_reponse_invalide_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            parse_position_response("OK")
        with pytest.raises(ValueError):
            parse_position_response("AZ12.0")  # champ EL manquant
