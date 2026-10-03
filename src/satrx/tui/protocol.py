from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------------
# Detection de protocole a partir du sidecar JSON
# -------------------------------------------------------------------------

LRPT_FREQ_MHZ = (137.1, 138.0)   # bande LRPT Meteor-M
APT_FREQ_MHZ  = (137.0, 138.0)   # bande APT NOAA (meme bande, distingue par symbol rate)
HRPT_FREQ_MHZ = (1690.0, 1710.0) # bande L HRPT
IRIDIUM_FREQ_MHZ = (1616.0, 1627.0)
GMR1_FREQ_MHZ = (1518.0, 1660.0) # Inmarsat / Thuraya bande L

LRPT_MIN_SRATE_MSPS = 0.5  # en dessous -> surement APT (< 50 ksps) ou signal etroit
APT_SRATE_KSPS_MAX  = 200  # APT utilise ~50 ksps


class ProtocolInfo:
    __slots__ = (
        "name", "modulation", "symbol_rate_kbps", "fec", "frame_sync",
        "center_freq_mhz", "auto_detected",
    )

    def __init__(
        self,
        name: str,
        modulation: str,
        symbol_rate_kbps: str,
        fec: str,
        frame_sync: str,
        center_freq_mhz: float,
        auto_detected: bool = True,
    ) -> None:
        self.name = name
        self.modulation = modulation
        self.symbol_rate_kbps = symbol_rate_kbps
        self.fec = fec
        self.frame_sync = frame_sync
        self.center_freq_mhz = center_freq_mhz
        self.auto_detected = auto_detected


def detect_protocol(sidecar_path: Path) -> Optional[ProtocolInfo]:
    """
    Detecte le protocole a partir du sidecar JSON d'une capture.
    Retourne None si le protocole ne peut pas etre determine.
    """
    if not sidecar_path.exists():
        return None

    try:
        data = json.loads(sidecar_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    freq_hz = float(data.get("center_freq_hz", 0))
    srate_hz = float(data.get("sample_rate_hz", 0))
    freq_mhz = freq_hz / 1e6
    srate_ksps = srate_hz / 1e3

    if LRPT_FREQ_MHZ[0] <= freq_mhz <= LRPT_FREQ_MHZ[1]:
        if srate_ksps >= APT_SRATE_KSPS_MAX:
            return ProtocolInfo(
                name="LRPT",
                modulation="QPSK (72 kBd)",
                symbol_rate_kbps="72",
                fec="Viterbi K=7 (171,133) + RS(255,223) x4",
                frame_sync="ASM 0x1ACFFC1D / CADU 1024 octets",
                center_freq_mhz=freq_mhz,
            )
        else:
            return ProtocolInfo(
                name="APT",
                modulation="FM analogique (2400 Hz sous-porteuse)",
                symbol_rate_kbps="-",
                fec="- (analogique)",
                frame_sync="sync word 7 bits / ligne 2080 pixels",
                center_freq_mhz=freq_mhz,
            )

    if HRPT_FREQ_MHZ[0] <= freq_mhz <= HRPT_FREQ_MHZ[1]:
        return ProtocolInfo(
            name="HRPT",
            modulation="BPSK (665.4 kbps)",
            symbol_rate_kbps="665",
            fec="Reed-Solomon (223,255)",
            frame_sync="ASM CCSDS / trame 11090 octets",
            center_freq_mhz=freq_mhz,
        )

    if IRIDIUM_FREQ_MHZ[0] <= freq_mhz <= IRIDIUM_FREQ_MHZ[1]:
        return ProtocolInfo(
            name="Iridium",
            modulation="QPSK / DQPSK (25 kbps par canal)",
            symbol_rate_kbps="25",
            fec="Convolutionnel + entrelacement",
            frame_sync="burst TDMA 8.28 ms",
            center_freq_mhz=freq_mhz,
        )

    if GMR1_FREQ_MHZ[0] <= freq_mhz <= GMR1_FREQ_MHZ[1]:
        return ProtocolInfo(
            name="GMR-1 / GMR-2 (Inmarsat/Thuraya)",
            modulation="GMSK (BT=0.3, 23.4 kbps)",
            symbol_rate_kbps="23.4",
            fec="Convolutionnel + entrelacement TDMA",
            frame_sync="burst normal : 3+39+64+39+3 bits",
            center_freq_mhz=freq_mhz,
        )

    return None


# -------------------------------------------------------------------------
# Detection de lisibilite d'un fichier image
# -------------------------------------------------------------------------

class ReadabilityResult:
    __slots__ = ("readable", "status", "entropy")

    def __init__(self, readable: Optional[bool], status: str, entropy: Optional[float]) -> None:
        self.readable = readable   # None = pas encore d'image
        self.status = status
        self.entropy = entropy


def check_image_readability(image_path: Path) -> ReadabilityResult:
    """
    Verifie si un fichier image est lisible (PNG/JPEG valide) ou chiffre/corrompu.
    Utilise Pillow si disponible, avec fallback sur la verification d'en-tete magique.
    """
    if not image_path.exists():
        return ReadabilityResult(readable=None, status="-", entropy=None)

    # Verification de l'en-tete magique
    try:
        with image_path.open("rb") as f:
            header = f.read(16)
    except OSError:
        return ReadabilityResult(readable=False, status="erreur lecture", entropy=None)

    is_png  = header[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpeg = header[:3] == b"\xff\xd8\xff"

    if not (is_png or is_jpeg):
        # En-tete invalide : on calcule l'entropie pour distinguer chiffre / corrompu
        entropy = _fast_entropy(image_path)
        if entropy is not None and entropy > 7.5:
            return ReadabilityResult(readable=False, status="chiffre ?", entropy=entropy)
        return ReadabilityResult(readable=False, status="corrompu", entropy=entropy)

    # En-tete valide : essai d'ouverture avec Pillow
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img.verify()
        return ReadabilityResult(readable=True, status="OK", entropy=None)
    except ImportError:
        # Pillow absent : on se fie a l'en-tete
        return ReadabilityResult(readable=True, status="OK (header)", entropy=None)
    except Exception:
        entropy = _fast_entropy(image_path)
        return ReadabilityResult(readable=False, status="corrompu", entropy=entropy)


def _fast_entropy(path: Path, sample_bytes: int = 65536) -> Optional[float]:
    """Entropie de Shannon sur les premiers sample_bytes du fichier."""
    import math
    from collections import Counter

    try:
        with path.open("rb") as f:
            data = f.read(sample_bytes)
    except OSError:
        return None

    if not data:
        return None

    counts = Counter(data)
    n = len(data)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return entropy


# -------------------------------------------------------------------------
# Classification de chiffrement / FEC
# -------------------------------------------------------------------------

def classify_encoding(entropy: float) -> tuple[str, str]:
    """
    Retourne (label, style Rich) pour une valeur d'entropie.
    Utilise les memes seuils que security/entropy.py.
    """
    if entropy >= 7.5:
        return "chiffre / compresse", "bold #E05050"
    if entropy >= 6.0:
        return "compresse / structure", "bold #E2934A"
    return "clair / structure", "bold #4DC88A"
