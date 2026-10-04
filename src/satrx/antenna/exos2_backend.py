"""Backend serie pour la monture equatoriale Bresser EXOS-II (protocole binaire proprietaire).

Protocole determine par reverse-engineering (source : indi-bresserexos2) :
- Trame 13 octets : header 0x55 0xAA 0x01 0x09 + commande (1B) + args (8B)
- Coordonnees equatoriales (AR en heures decimales, Dec en degres decimaux)
- Debit serie : 9600 bauds, 8N1
- Le mount envoie des trames 0xFF en continu avec sa position courante

Ce backend implemente le protocole CommandBackend (typage structurel) defini dans
rotator.py. Il convertit les commandes AZ/EL de RotatorController en AR/Dec
en utilisant les coordonnees de l'observateur et l'heure UTC courante.
"""

import datetime
import math
import re
import struct
from typing import Any, Optional

# Trame header fixe (firmware v2.3)
_FRAME_HEADER: bytes = bytes([0x55, 0xAA, 0x01, 0x09])
_FRAME_SIZE: int = 13
_PAYLOAD_SIZE: int = 8

# Identifiants de commande
_CMD_STOP: int = 0x1D
_CMD_PARK: int = 0x1E
_CMD_GET_SITE_LOCATION: int = 0x1F  # declenche les rapports de position 0xFF
_CMD_DISCONNECT: int = 0x22
_CMD_GOTO: int = 0x23
_CMD_POSITION_REPORT: int = 0xFF

BAUD_RATE: int = 9600

_RE_AZEL = re.compile(r"AZ\s*(?P<az>[\d.]+)\s+EL\s*(?P<el>[\d.]+)")


# ---------------------------------------------------------------------------
# Construction de trames binaires
# ---------------------------------------------------------------------------

def build_goto_frame(ra_hours: float, dec_deg: float) -> bytes:
    """Construit une trame GOTO de 13 octets.

    ra_hours : AR en heures decimales [0, 24[
    dec_deg  : declinaison en degres [-90, 90]
    """
    if not 0.0 <= ra_hours < 24.0:
        raise ValueError(f"AR hors plage [0, 24[ : {ra_hours}")
    if not -90.0 <= dec_deg <= 90.0:
        raise ValueError(f"Dec hors plage [-90, 90] : {dec_deg}")
    payload = struct.pack("<ff", ra_hours, dec_deg)
    return _FRAME_HEADER + bytes([_CMD_GOTO]) + payload


def build_stop_frame() -> bytes:
    """Trame STOP (arret immediat du slew)."""
    return _FRAME_HEADER + bytes([_CMD_STOP]) + bytes(_PAYLOAD_SIZE)


def build_park_frame() -> bytes:
    """Trame PARK (retour en position initiale)."""
    return _FRAME_HEADER + bytes([_CMD_PARK]) + bytes(_PAYLOAD_SIZE)


def build_disconnect_frame() -> bytes:
    """Trame DISCONNECT (arret propre de l'echange serie)."""
    return _FRAME_HEADER + bytes([_CMD_DISCONNECT]) + bytes(_PAYLOAD_SIZE)


def build_get_site_location_frame() -> bytes:
    """Trame GET_SITE_LOCATION (0x1F).

    Envoyer cette trame apres la connexion serie pour declencher les rapports
    de position 0xFF en continu par la monture (sequence d'init obligatoire).
    """
    return _FRAME_HEADER + bytes([_CMD_GET_SITE_LOCATION]) + bytes(_PAYLOAD_SIZE)


def parse_position_frame(data: bytes) -> tuple[float, float]:
    """Decode une trame de rapport de position (0xFF) en (AR_heures, Dec_deg).

    Leve ValueError si la trame est invalide ou n'est pas un rapport de position.
    """
    if len(data) < _FRAME_SIZE:
        raise ValueError(f"Trame trop courte : {len(data)} octets (attendu {_FRAME_SIZE})")
    if data[:4] != _FRAME_HEADER:
        raise ValueError(f"Header invalide : {data[:4].hex()}")
    if data[4] != _CMD_POSITION_REPORT:
        raise ValueError(f"Commande inattendue : 0x{data[4]:02X} (attendu 0xFF)")
    ra, dec = struct.unpack_from("<ff", data, offset=5)
    return float(ra), float(dec)


# ---------------------------------------------------------------------------
# Conversion de coordonnees horizontales <-> equatoriales
# ---------------------------------------------------------------------------

def _julian_date(utc: datetime.datetime) -> float:
    """Calcule la date julienne depuis un datetime UTC."""
    a = (14 - utc.month) // 12
    y = utc.year + 4800 - a
    m = utc.month + 12 * a - 3
    jdn = (utc.day + (153 * m + 2) // 5 + 365 * y
           + y // 4 - y // 100 + y // 400 - 32045)
    frac = ((utc.hour - 12) / 24.0 + utc.minute / 1440.0
            + utc.second / 86400.0 + utc.microsecond / 86_400_000_000.0)
    return float(jdn) + frac


def _local_sidereal_time(lon_deg: float, utc: datetime.datetime) -> float:
    """Temps sidereal local en heures decimales.

    lon_deg positif vers l'est (ex: Paris ~ +2.35).
    """
    jd = _julian_date(utc)
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = (280.46061837
                + 360.98564736629 * (jd - 2451545.0)
                + 0.000387933 * t * t
                - t * t * t / 38710000.0) % 360.0
    lst_hours = (gmst_deg / 15.0 + lon_deg / 15.0) % 24.0
    return lst_hours


def azel_to_radec(
    az_deg: float,
    el_deg: float,
    lat_deg: float,
    lon_deg: float,
    utc: datetime.datetime,
) -> tuple[float, float]:
    """Convertit coordonnees horizontales (AZ/EL) en equatoriales (AR/Dec).

    Retourne (ra_hours, dec_deg). Leve ValueError si el_deg hors [-90, 90].
    """
    if not -90.0 <= el_deg <= 90.0:
        raise ValueError(f"Elevation hors plage : {el_deg}")

    az = math.radians(az_deg)
    el = math.radians(el_deg)
    lat = math.radians(lat_deg)

    sin_dec = (math.sin(el) * math.sin(lat)
               + math.cos(el) * math.cos(lat) * math.cos(az))
    dec_rad = math.asin(max(-1.0, min(1.0, sin_dec)))

    # cos(lat) au numerateur : derive de la formule standard atan2(sin(H), cos(H))
    # ou sin(H) = -sin(Az)*cos(alt)/cos(dec) et cos(H) = [...]/cos(lat)/cos(dec).
    # Apres simplification par cos(dec) > 0, il reste cos(lat) au numerateur.
    ha_rad = math.atan2(
        -math.sin(az) * math.cos(el) * math.cos(lat),
        math.sin(el) - math.sin(lat) * sin_dec,
    )

    lst_hours = _local_sidereal_time(lon_deg, utc)
    ra_hours = (lst_hours - math.degrees(ha_rad) / 15.0) % 24.0

    return ra_hours, math.degrees(dec_rad)


def radec_to_azel(
    ra_hours: float,
    dec_deg: float,
    lat_deg: float,
    lon_deg: float,
    utc: datetime.datetime,
) -> tuple[float, float]:
    """Convertit coordonnees equatoriales (AR/Dec) en horizontales (AZ/EL).

    Retourne (az_deg, el_deg). Angle horaire calcule depuis le TSL courant.
    """
    lst_hours = _local_sidereal_time(lon_deg, utc)
    ha_rad = math.radians((lst_hours - ra_hours) * 15.0)
    dec = math.radians(dec_deg)
    lat = math.radians(lat_deg)

    sin_el = (math.sin(dec) * math.sin(lat)
              + math.cos(dec) * math.cos(lat) * math.cos(ha_rad))
    el_rad = math.asin(max(-1.0, min(1.0, sin_el)))

    # Formule explicite issue de Meeus (conv. Az depuis Nord, sens horaire) :
    # sin(Az) = -sin(H)*cos(dec)/cos(alt), cos(Az) = [sin(dec)-sin(lat)*sin(alt)]/[cos(lat)*cos(alt)]
    # Apres simplification par cos(alt) > 0.
    az_rad = math.atan2(
        -math.cos(dec) * math.sin(ha_rad),
        math.sin(dec) * math.cos(lat) - math.cos(dec) * math.cos(ha_rad) * math.sin(lat),
    )
    az_deg = math.degrees(az_rad) % 360.0

    return az_deg, math.degrees(el_rad)


# ---------------------------------------------------------------------------
# Backend EXOS-II
# ---------------------------------------------------------------------------

class ExosIIBackend:
    """Backend CommandBackend pour la monture Bresser EXOS-II.

    Traduit les commandes AZ/EL textuelles du RotatorController en trames
    binaires AR/Dec envoyees sur le port serie de la monture.

    Parametres
    ----------
    port         : chemin du port serie (ex: '/dev/ttyUSB0')
    observer_lat : latitude de l'observateur en degres decimaux
    observer_lon : longitude de l'observateur en degres decimaux (+ vers l'est)
    baud_rate    : debit serie (defaut 9600)
    timeout      : timeout de lecture en secondes
    """

    def __init__(
        self,
        port: str,
        observer_lat: float,
        observer_lon: float,
        baud_rate: int = BAUD_RATE,
        timeout: float = 2.0,
    ) -> None:
        self._port = port
        self._lat = observer_lat
        self._lon = observer_lon
        self._baud = baud_rate
        self._timeout = timeout
        self._serial: Optional[Any] = None

    def connect(self) -> None:
        """Ouvre le port serie et demarre les rapports de position.

        RTS et DTR doivent etre asserts pour que la monture accepte les trames.
        GET_SITE_LOCATION (0x1F) est ensuite envoye : la monture repond avec
        0xFE (coordonnees du site) puis commence a emettre des 0xFF en continu.
        """
        import serial
        self._serial = serial.Serial(
            self._port,
            baudrate=self._baud,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self._timeout,
            rtscts=False,
            dsrdtr=False,
        )
        self._serial.setRTS(True)
        self._serial.setDTR(True)
        self._serial.reset_input_buffer()
        self._serial.write(build_get_site_location_frame())

    def disconnect(self) -> None:
        """Envoie DISCONNECT puis ferme le port serie."""
        if self._serial is not None:
            s = self._serial
            if getattr(s, "is_open", False):
                s.write(build_disconnect_frame())
                s.close()
        self._serial = None

    def send_command(self, command: str) -> str:
        """Traduit une commande AZ/EL textuelle en trame EXOS-II binaire.

        Formats acceptes :
        - "AZ<az> EL<el>" : slew vers cet azimut/elevation (converti en AR/Dec)
        - "HOME" ou "AZ0.0 EL0.0" : park
        - "STOP" : arret du mouvement

        Retourne "OK" en cas de succes, "ERROR:<detail>" sinon.
        """
        if self._serial is None:
            return "ERROR:non connecte"

        command = command.strip().upper()

        if command == "STOP":
            self._serial.write(build_stop_frame())
            return "OK"

        if command in ("HOME", "PARK"):
            self._serial.write(build_park_frame())
            return "OK"

        m = _RE_AZEL.match(command)
        if not m:
            return f"ERROR:commande inconnue ({command!r})"

        az = float(m.group("az"))
        el = float(m.group("el"))

        utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        try:
            ra, dec = azel_to_radec(az, el, self._lat, self._lon, utc)
        except ValueError as exc:
            return f"ERROR:{exc}"

        try:
            frame = build_goto_frame(ra, dec)
        except ValueError as exc:
            return f"ERROR:{exc}"

        self._serial.write(frame)
        return "OK"

    def get_position(self) -> str:
        """Lit la prochaine trame de position (0xFF) et la retourne en AZ/EL.

        Retourne "AZ<az> EL<el>" ou "ERROR:<detail>" si aucune trame valide
        n'est recue dans le timeout configure.
        """
        if self._serial is None:
            return "ERROR:non connecte"

        # Consommer les trames jusqu'a trouver un rapport de position 0xFF.
        # La monture peut envoyer d'abord 0xFE (site location) avant les 0xFF.
        for _ in range(8):
            raw = self._serial.read(_FRAME_SIZE)
            if len(raw) < _FRAME_SIZE:
                return "ERROR:timeout - aucune trame recue"
            if len(raw) >= 5 and raw[:4] == _FRAME_HEADER and raw[4] == _CMD_POSITION_REPORT:
                break
        else:
            return "ERROR:aucune trame 0xFF recue"

        try:
            ra, dec = parse_position_frame(raw)
        except ValueError as exc:
            return f"ERROR:{exc}"

        utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        az, el = radec_to_azel(ra, dec, self._lat, self._lon, utc)
        return f"AZ{az:.1f} EL{el:.1f}"
