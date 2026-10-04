from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareStatus:
    hackrf_detected: bool
    hackrf_fw: str
    rtlsdr_detected: bool
    rtlsdr_count: int
    exos2_detected: bool
    exos2_port: str


def detect_hardware(timeout: float = 3.0, rotator_port: str = "") -> HardwareStatus:
    """Detection non-bloquante du materiel SDR et rotateur connectes."""
    hackrf_detected = False
    hackrf_fw = ""
    rtlsdr_detected = False
    rtlsdr_count = 0

    try:
        result = subprocess.run(
            ["hackrf_info"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and "HackRF" in result.stdout:
            hackrf_detected = True
            for line in result.stdout.splitlines():
                if "Firmware Version" in line:
                    hackrf_fw = line.split(":", 1)[-1].strip()
                    break
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        result = subprocess.run(
            ["rtl_test", "-t"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if "Found" in output and "device" in output.lower():
            rtlsdr_detected = True
            for line in output.splitlines():
                if "Found" in line and "device" in line.lower():
                    try:
                        rtlsdr_count = int(line.split()[1])
                    except (IndexError, ValueError):
                        rtlsdr_count = 1
                    break
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    exos2_ok = detect_exos2(rotator_port, timeout=1.5) if rotator_port else False

    return HardwareStatus(
        hackrf_detected=hackrf_detected,
        hackrf_fw=hackrf_fw,
        rtlsdr_detected=rtlsdr_detected,
        rtlsdr_count=rtlsdr_count,
        exos2_detected=exos2_ok,
        exos2_port=rotator_port,
    )


def detect_exos2(port: str, timeout: float = 1.5) -> bool:
    """Tente d'ouvrir le port serie et verifie que la monture EXOS-II repond.

    Envoie GET_SITE_LOCATION (0x1F) et controle que la reponse commence par
    le header binaire 0x55 0xAA 0x01 0x09. Ferme le port dans tous les cas.
    Retourne False si le port est absent, occupe ou si la monture ne repond pas.
    """
    if not port:
        return False
    try:
        import serial
        from satrx.antenna.exos2_backend import (
            _FRAME_HEADER,
            _FRAME_SIZE,
            build_get_site_location_frame,
        )

        ser = serial.Serial(
            port,
            baudrate=9600,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
            rtscts=False,
            dsrdtr=False,
        )
        ser.setRTS(True)
        ser.setDTR(True)
        ser.reset_input_buffer()
        ser.write(build_get_site_location_frame())
        raw = ser.read(_FRAME_SIZE)
        ser.close()
        return len(raw) >= 4 and raw[:4] == _FRAME_HEADER
    except Exception:
        return False


def suggest_antenna(center_freq_hz: float) -> list[str]:
    freq_mhz = center_freq_hz / 1e6

    if freq_mhz < 300:
        suggestions = [
            f"Bande VHF ({freq_mhz:.1f} MHz)",
            "Antenne QFH 137 MHz recommandee (ex. Diamond DP-KE137, ~60 EUR)",
            f"Dipole demi-onde : longueur totale ~{(300 / freq_mhz / 2 * 100):.0f} cm",
            "Alternative : antenne TV de reception TDT (non optimale sous 174 MHz)",
        ]
    elif freq_mhz < 3000:
        suggestions = [
            f"Bande L/S ({freq_mhz:.0f} MHz)",
            "Antenne directionnelle requise : Yagi ou parabole/grille",
            "Compatible antenne WiFi 2.4/5.8 GHz de type directionnelle",
            "Gain conseille : >= 10 dBi (Yagi) ou >= 15 dBi (parabole)",
        ]
    else:
        suggestions = [
            f"Frequence elevee ({freq_mhz:.0f} MHz)",
            "Downconverter LNB requis (bande Ku : 10.7-12.75 GHz -> IF 950-2150 MHz)",
            "Alimentation fantome necessaire : 13 V ou 18 V sur le coax (bias-tee externe)",
            "Le HackRF seul ne peut pas couvrir cette bande directement",
        ]

    return suggestions


def format_hardware_panel(hw: HardwareStatus, freq_hz: float) -> str:
    """Retourne un texte Rich formate pour le panneau de detection materiel."""
    lines: list[str] = []

    if hw.hackrf_detected:
        fw = f"  FW {hw.hackrf_fw}" if hw.hackrf_fw else ""
        lines.append(f"[bold #4DC88A]✓  HackRF One[/]  detecte (USB){fw}")
    else:
        lines.append("[bold #E2934A]✗  HackRF One[/]  non detecte - verifier USB")

    if hw.rtlsdr_detected:
        lines.append(f"[bold #4DC88A]✓  RTL-SDR[/]  {hw.rtlsdr_count} peripherique(s) detecte(s)")
    else:
        lines.append("[dim]·  RTL-SDR       non detecte[/]")

    if hw.exos2_port:
        if hw.exos2_detected:
            lines.append(
                f"[bold #4DC88A]✓  EXOS-II[/]  repond sur {hw.exos2_port}"
            )
        else:
            lines.append(
                f"[bold #E2934A]✗  EXOS-II[/]  pas de reponse sur {hw.exos2_port} "
                f"(monture eteinte ou port incorrect)"
            )
    else:
        lines.append("[dim]·  EXOS-II       port non configure (onglet Config)[/]")

    lines.append("")
    lines.append("[bold #1EB8A0]Antenne :[/]")
    for sug in suggest_antenna(freq_hz):
        lines.append(f"  {sug}")

    return "\n".join(lines)
