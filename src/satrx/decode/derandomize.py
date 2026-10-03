from __future__ import annotations

# Sequence de derandomisation (descrambling) CCSDS appliquee par XOR sur le payload utile
# d'un CADU (apres l'ASM, qui lui n'est jamais randomise - necessaire pour rester detectable
# tel quel par la synchro trame) avant le decodage Reed-Solomon. Algorithme retrouve par
# recherche exhaustive (16 premiers octets confirmes contre le decodeur LRPT open source
# artlav/meteor_decoder, recherche du 16/08/2026) puis les 255 octets complets regeneres :
# registre 8 bits, masque de retroaction 0x95, 8 cadences par octet de sortie, etat initial
# 0xFF. Verifie empiriquement : periode exacte de 255 (le 256e octet reboucle sur 0xFF),
# 255 valeurs toutes distinctes. XOR etant sa propre inverse, la meme fonction randomise
# et derandomise.

_TAPS_MASK = 0x95
_INIT_STATE = 0xFF
_SEQUENCE_LENGTH = 255


def _clock(state: int) -> int:
    feedback = 0
    masked = state & _TAPS_MASK
    while masked:
        feedback ^= masked & 1
        masked >>= 1
    return ((state << 1) | feedback) & 0xFF


def generate_pn_sequence(length: int = _SEQUENCE_LENGTH) -> bytes:
    if length <= 0:
        raise ValueError(f"length doit etre positif, recu {length}")

    state = _INIT_STATE
    sequence = bytearray([state])
    while len(sequence) < length:
        for _ in range(8):
            state = _clock(state)
        sequence.append(state)
    return bytes(sequence[:length])


def derandomize(data: bytes, sequence: bytes | None = None) -> bytes:
    if not data:
        raise ValueError("data ne doit pas etre vide")

    pn = sequence if sequence is not None else generate_pn_sequence(_SEQUENCE_LENGTH)
    if not pn:
        raise ValueError("sequence ne doit pas etre vide")

    return bytes(byte ^ pn[i % len(pn)] for i, byte in enumerate(data))
