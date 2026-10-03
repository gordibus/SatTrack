"""Couche I/O serie vers l'Arduino Nano du rotateur (F9).

Le protocole (firmware Hamlib-compatible pre-flash) est en ASCII, 9600 baud,
lignes terminees par LF (``\\n``) :

    PC -> Arduino        Arduino -> PC
    "AZ127.4 EL42.6\\n"   "OK\\n"
    "HOME\\n"             "OK\\n"
    "PARK\\n"             "OK\\n"
    "STOP\\n"             "OK\\n"
    "GET\\n"              "AZ127.4 EL42.6\\n"

La logique pure (formatage de commande, parsing de reponse) est isolee au
niveau module pour etre testable sans materiel. Seule la classe
:class:`SerialBackend` touche le port serie ; elle est couverte par les tests
d'integration (``tests/integration/``, Arduino branche requis).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from satrx.antenna.rotator import AzElPosition, RotatorTimeoutError

if TYPE_CHECKING:
    import serial as _serial

# "AZ127.4 EL42.6" ou "AZ-3.0 EL0.5", espaces multiples toleres.
_POSITION_RE = re.compile(
    r"^AZ\s*(?P<az>[-+]?\d+(?:\.\d+)?)\s+EL\s*(?P<el>[-+]?\d+(?:\.\d+)?)\s*$"
)


def format_goto_command(az_deg: float, el_deg: float) -> str:
    """Construit la trame de deplacement ``AZ<az> EL<el>`` (sans le LF final).

    Le LF de terminaison est ajoute par :meth:`SerialBackend.send_command`.

    >>> format_goto_command(127.4, 42.6)
    'AZ127.4 EL42.6'
    """
    return f"AZ{az_deg:.1f} EL{el_deg:.1f}"


def parse_position_response(response: str) -> AzElPosition:
    """Parse une reponse ``AZ<az> EL<el>`` (reponse a la commande ``GET``).

    Leve :class:`ValueError` si la reponse ne correspond pas au format attendu
    (jamais de retour ``None`` silencieux).

    >>> parse_position_response("AZ127.4 EL42.6")
    AzElPosition(az_deg=127.4, el_deg=42.6)
    """
    match = _POSITION_RE.match(response.strip())
    if match is None:
        raise ValueError(f"Reponse de position invalide : {response!r}")
    return AzElPosition(az_deg=float(match.group("az")), el_deg=float(match.group("el")))


class SerialBackend:
    """Couche I/O serie vers l'Arduino, isolee pour permettre le test sans materiel.

    L'import de ``pyserial`` est differe a :meth:`connect` : le reste du module
    (fonctions pures, construction de l'objet) reste importable meme sur une
    machine sans le paquet, et les tests unitaires n'ouvrent aucun port.
    """

    def __init__(
        self, port: str = "/dev/ttyUSB0", baud: int = 9600, timeout_s: float = 2.0
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout_s = timeout_s
        self._serial: _serial.Serial | None = None

    def connect(self) -> None:
        """Ouvre le port serie. Leve ``serial.SerialException`` si echec."""
        import serial

        self._serial = serial.Serial(
            port=self.port, baudrate=self.baud, timeout=self.timeout_s
        )

    def disconnect(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def send_command(self, cmd: str) -> str:
        """Envoie ``cmd + '\\n'``, attend la reponse, retourne la reponse strippee.

        Leve :class:`RotatorTimeoutError` si ``timeout_s`` s'ecoule sans reponse
        (``readline`` renvoie une ligne vide), :class:`ConnectionError` si le
        port n'est pas ouvert.
        """
        if self._serial is None or not self._serial.is_open:
            raise ConnectionError("Port serie non connecte : appeler connect() d'abord")

        self._serial.write((cmd + "\n").encode("ascii"))
        self._serial.flush()
        raw: bytes = self._serial.readline()
        if not raw:
            raise RotatorTimeoutError(
                f"Aucune reponse a {cmd!r} apres {self.timeout_s}s"
            )
        return raw.decode("ascii", errors="replace").strip()
