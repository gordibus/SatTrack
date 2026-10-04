"""Test de communication serie avec la monture Bresser EXOS-II.

Sequence :
  1. Ouverture du port + envoi GET_SITE_LOCATION (declenche les 0xFF)
  2. Lecture raw 5s pour diagnostiquer ce que la monture envoie
  3. Lecture de 3 trames de position parseees
  4. (optionnel) GOTO vers AZ=180 EL=30 (Sud, 30 deg)
  5. STOP + deconnexion

Usage :
  poetry run python scripts/test_exos2_move.py
  poetry run python scripts/test_exos2_move.py --no-goto
  poetry run python scripts/test_exos2_move.py --port /dev/ttyUSB1
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import serial as pyserial

from satrx.antenna.exos2_backend import (
    ExosIIBackend,
    _CMD_POSITION_REPORT,
    _FRAME_HEADER,
    _FRAME_SIZE,
    azel_to_radec,
    build_get_site_location_frame,
    build_stop_frame,
    parse_position_frame,
    radec_to_azel,
)

LAT = 48.9101
LON = 2.2549

CIBLE_AZ = 180.0
CIBLE_EL = 30.0


def scan_port_raw(port: str, timeout_s: float = 5.0) -> bytes:
    """Ouvre le port, envoie GET_SITE_LOCATION, lit les octets bruts recus."""
    s = pyserial.Serial(port, baudrate=9600, bytesize=8, parity="N", stopbits=1, timeout=timeout_s)
    s.write(build_get_site_location_frame())
    time.sleep(0.2)
    data = s.read(256)
    s.close()
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Test EXOS-II - connexion et mouvement")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--no-goto", action="store_true", help="Ne pas envoyer de GOTO")
    parser.add_argument("--lat", type=float, default=LAT)
    parser.add_argument("--lon", type=float, default=LON)
    args = parser.parse_args()

    # --- Diagnostic raw ---
    print(f"[DIAGNOSTIC] Scan raw sur {args.port} (5s apres GET_SITE_LOCATION)...")
    try:
        raw = scan_port_raw(args.port, timeout_s=5.0)
    except Exception as exc:
        print(f"  ✖ Impossible d'ouvrir le port : {exc}")
        print("  Verifier : sudo usermod -aG dialout $USER  et reconnexion de session")
        sys.exit(1)

    if not raw:
        print("  ✖ Aucun octet recu.")
        print("  -> Monture probablement eteinte. Allumer la monture et relancer.")
        sys.exit(1)

    print(f"  ✓ {len(raw)} octets recus")
    print(f"  Hex : {raw.hex()}")

    trame_ok = any(
        raw[i:i+4] == _FRAME_HEADER and len(raw) >= i + _FRAME_SIZE and raw[i+4] == _CMD_POSITION_REPORT
        for i in range(len(raw) - _FRAME_SIZE + 1)
    )
    if trame_ok:
        print("  ✓ Trames 0xFF de position detectees - protocole confirme")
    else:
        print("  ⚠ Octets recus mais pas de trame 0xFF reconnue - header attendu : 55 AA 01 09 FF")

    # --- Connexion via backend ---
    print(f"\n[1/4] Connexion backend sur {args.port}...")
    backend = ExosIIBackend(
        port=args.port,
        observer_lat=args.lat,
        observer_lon=args.lon,
        baud_rate=9600,
        timeout=5.0,
    )
    try:
        backend.connect()
        print("  ✓ Connecte (GET_SITE_LOCATION envoye)")
    except Exception as exc:
        print(f"  ✖ {exc}")
        sys.exit(1)

    time.sleep(0.5)

    # --- STOP de securite ---
    print("\n[2/4] STOP de securite...")
    r = backend.send_command("STOP")
    print(f"  -> {r}")
    time.sleep(0.3)

    # --- Lecture position ---
    print("\n[3/4] Lecture de 3 trames de position...")
    for i in range(3):
        result = backend.get_position()
        if result.startswith("ERROR"):
            print(f"  [trame {i+1}] {result}")
        else:
            print(f"  [trame {i+1}] ✓ {result}")

    # --- GOTO ---
    if not args.no_goto:
        utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        ra, dec = azel_to_radec(CIBLE_AZ, CIBLE_EL, args.lat, args.lon, utc)
        print(f"\n[4/4] GOTO AZ={CIBLE_AZ} EL={CIBLE_EL}")
        print(f"  => AR={ra:.3f}h  Dec={dec:.2f} deg")
        r = backend.send_command(f"AZ{CIBLE_AZ} EL{CIBLE_EL}")
        print(f"  -> {r}")
        if r == "OK":
            print("  Attente 4s puis lecture position de confirmation...")
            time.sleep(4.0)
            for i in range(2):
                result = backend.get_position()
                print(f"  [confirm {i+1}] {result}")
    else:
        print("\n[4/4] --no-goto active, GOTO ignore.")

    # --- Fermeture propre ---
    print("\nSTOP final + deconnexion...")
    backend.send_command("STOP")
    backend.disconnect()
    print("✓ Termine.")


if __name__ == "__main__":
    main()
