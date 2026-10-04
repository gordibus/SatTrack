"""Tests unitaires pour le backend Bresser EXOS-II.

Valide : construction des trames binaires, conversion AZ/EL <-> AR/Dec,
et la logique de commande du backend (sans materiel).
"""

import datetime
import math
import struct

import pytest

from satrx.antenna.exos2_backend import (
    BAUD_RATE,
    ExosIIBackend,
    _FRAME_HEADER,
    _CMD_GOTO,
    _CMD_STOP,
    _CMD_PARK,
    _CMD_DISCONNECT,
    _CMD_POSITION_REPORT,
    _FRAME_SIZE,
    azel_to_radec,
    build_goto_frame,
    build_park_frame,
    build_stop_frame,
    parse_position_frame,
    radec_to_azel,
)

# Coordonnees de reference : Paris (Saint-Denis)
LAT = 48.9101
LON = 2.2549

# Heure UTC fixe pour reproductibilite des tests
UTC_REF = datetime.datetime(2026, 9, 23, 12, 0, 0)


class TestBuildGoToFrame:

    def test_structure_13_octets(self) -> None:
        frame = build_goto_frame(6.5, 30.0)
        assert len(frame) == _FRAME_SIZE

    def test_header_correct(self) -> None:
        frame = build_goto_frame(6.5, 30.0)
        assert frame[:4] == _FRAME_HEADER

    def test_commande_id_goto(self) -> None:
        frame = build_goto_frame(6.5, 30.0)
        assert frame[4] == _CMD_GOTO

    def test_payload_floats_little_endian(self) -> None:
        ra, dec = 6.5, 30.0
        frame = build_goto_frame(ra, dec)
        ra_decoded, dec_decoded = struct.unpack_from("<ff", frame, offset=5)
        assert abs(ra_decoded - ra) < 1e-5
        assert abs(dec_decoded - dec) < 1e-5

    def test_ra_hors_plage_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            build_goto_frame(24.1, 0.0)

    def test_dec_hors_plage_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            build_goto_frame(12.0, 91.0)

    def test_ra_negatif_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            build_goto_frame(-1.0, 0.0)


class TestBuildControlFrames:

    def test_stop_frame_taille(self) -> None:
        assert len(build_stop_frame()) == _FRAME_SIZE

    def test_stop_frame_commande(self) -> None:
        assert build_stop_frame()[4] == _CMD_STOP

    def test_park_frame_commande(self) -> None:
        assert build_park_frame()[4] == _CMD_PARK

    def test_stop_payload_zeros(self) -> None:
        assert build_stop_frame()[5:] == bytes(8)

    def test_park_payload_zeros(self) -> None:
        assert build_park_frame()[5:] == bytes(8)


class TestParsePositionFrame:

    def _make_position_frame(self, ra: float, dec: float) -> bytes:
        payload = struct.pack("<ff", ra, dec)
        return _FRAME_HEADER + bytes([_CMD_POSITION_REPORT]) + payload

    def test_decode_nominal(self) -> None:
        frame = self._make_position_frame(6.5, 30.0)
        ra, dec = parse_position_frame(frame)
        assert abs(ra - 6.5) < 1e-5
        assert abs(dec - 30.0) < 1e-5

    def test_trame_trop_courte(self) -> None:
        with pytest.raises(ValueError):
            parse_position_frame(bytes(10))

    def test_header_invalide(self) -> None:
        frame = bytes([0x00, 0x00, 0x00, 0x00]) + bytes(9)
        with pytest.raises(ValueError, match="Header invalide"):
            parse_position_frame(frame)

    def test_commande_inattendue(self) -> None:
        frame = _FRAME_HEADER + bytes([0x23]) + bytes(8)
        with pytest.raises(ValueError, match="Commande inattendue"):
            parse_position_frame(frame)


class TestAzelToRadec:

    def test_zenit_donne_dec_egale_latitude(self) -> None:
        """Au zenith (EL=90), la declinaison doit etre egale a la latitude."""
        ra, dec = azel_to_radec(0.0, 90.0, LAT, LON, UTC_REF)
        assert abs(dec - LAT) < 0.1

    def test_el_hors_plage_leve_valueerror(self) -> None:
        with pytest.raises(ValueError):
            azel_to_radec(0.0, 95.0, LAT, LON, UTC_REF)

    def test_ra_dans_plage_valide(self) -> None:
        ra, dec = azel_to_radec(180.0, 45.0, LAT, LON, UTC_REF)
        assert 0.0 <= ra < 24.0

    def test_dec_dans_plage_valide(self) -> None:
        ra, dec = azel_to_radec(90.0, 30.0, LAT, LON, UTC_REF)
        assert -90.0 <= dec <= 90.0


class TestRadecToAzel:

    def test_aller_retour_azel_radec(self) -> None:
        """AZ/EL -> AR/Dec -> AZ/EL doit conserver les coordonnees (meme temps UTC)."""
        az_in, el_in = 135.0, 45.0
        ra, dec = azel_to_radec(az_in, el_in, LAT, LON, UTC_REF)
        # La conversion retour doit utiliser le meme instant UTC pour que le TSL
        # soit identique et que le round-trip soit exact.
        az_out, el_out = radec_to_azel(ra, dec, LAT, LON, UTC_REF)
        assert abs(az_out - az_in) < 0.01
        assert abs(el_out - el_in) < 0.01

    def test_az_toujours_positif(self) -> None:
        ra, dec = azel_to_radec(270.0, 20.0, LAT, LON, UTC_REF)
        az, el = radec_to_azel(ra, dec, LAT, LON, UTC_REF)
        assert az >= 0.0


class TestExosIIBackendSansHardware:
    """Tests de la logique de commande sans port serie reel.

    Utilise un faux objet serie qui capture les octets ecrits.
    """

    class _FakeSerial:
        def __init__(self) -> None:
            self.written: list[bytes] = []
            self.is_open: bool = True
            self._read_buf: bytes = bytes()

        def write(self, data: bytes) -> None:
            self.written.append(data)

        def read(self, n: int) -> bytes:
            chunk = self._read_buf[:n]
            self._read_buf = self._read_buf[n:]
            return chunk

        def close(self) -> None:
            self.is_open = False

    def _make_backend(self) -> tuple["TestExosIIBackendSansHardware._FakeSerial", ExosIIBackend]:
        backend = ExosIIBackend("/dev/ttyUSB0", LAT, LON)
        fake = self._FakeSerial()
        backend._serial = fake
        return fake, backend

    def test_stop_envoie_trame_stop(self) -> None:
        fake, backend = self._make_backend()
        result = backend.send_command("STOP")
        assert result == "OK"
        assert len(fake.written) == 1
        assert fake.written[0][4] == _CMD_STOP

    def test_park_envoie_trame_park(self) -> None:
        fake, backend = self._make_backend()
        result = backend.send_command("PARK")
        assert result == "OK"
        assert fake.written[0][4] == _CMD_PARK

    def test_azel_envoie_trame_goto(self) -> None:
        fake, backend = self._make_backend()
        result = backend.send_command("AZ135.0 EL45.0")
        assert result == "OK"
        assert len(fake.written) == 1
        assert fake.written[0][4] == _CMD_GOTO
        assert len(fake.written[0]) == _FRAME_SIZE

    def test_commande_inconnue_retourne_error(self) -> None:
        _, backend = self._make_backend()
        result = backend.send_command("XYZZY")
        assert result.startswith("ERROR")

    def test_non_connecte_retourne_error(self) -> None:
        backend = ExosIIBackend("/dev/ttyUSB0", LAT, LON)
        result = backend.send_command("AZ90.0 EL30.0")
        assert result.startswith("ERROR")

    def test_get_position_parse_trame_position(self) -> None:
        fake, backend = self._make_backend()
        ra, dec = 6.5, 30.0
        payload = struct.pack("<ff", ra, dec)
        fake._read_buf = _FRAME_HEADER + bytes([_CMD_POSITION_REPORT]) + payload

        result = backend.get_position()
        assert result.startswith("AZ")
        assert "EL" in result

    def test_get_position_timeout_retourne_error(self) -> None:
        fake, backend = self._make_backend()
        fake._read_buf = bytes()
        result = backend.get_position()
        assert result.startswith("ERROR")

    def test_interop_send_command_puis_parse_goto(self) -> None:
        """La trame ecrite par send_command doit etre une trame GOTO valide."""
        fake, backend = self._make_backend()
        backend.send_command("AZ200.0 EL35.0")
        frame = fake.written[0]
        assert frame[:4] == _FRAME_HEADER
        assert frame[4] == _CMD_GOTO
        ra, dec = struct.unpack_from("<ff", frame, offset=5)
        assert 0.0 <= ra < 24.0
        assert -90.0 <= dec <= 90.0

    def test_baud_rate_par_defaut(self) -> None:
        backend = ExosIIBackend("/dev/ttyUSB0", LAT, LON)
        assert backend._baud == BAUD_RATE
