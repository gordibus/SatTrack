from __future__ import annotations

from dataclasses import dataclass

# ASM (Attached Sync Marker) CCSDS standard 32 bits, en tete de chaque CADU. Valeur
# confirmee pour Meteor-M LRPT (recherche du 16/08/2026, recoupee sur deux sources
# independantes) : 0x1ACFFC1D, appliquee AVANT codage convolutionnel.
DEFAULT_CCSDS_ASM = bytes.fromhex("1ACFFC1D")

# CADU Meteor-M/CCSDS standard : 1024 octets (8192 bits), ASM inclus. Confirme via une
# source technique METOP (meme convention CCSDS que Meteor-M, tous les autres parametres
# deja verifies correspondent au standard CCSDS classique) - a confirmer directement sur
# Meteor-M si une comparaison SatDump devient possible.
METEOR_LRPT_CADU_LENGTH_BITS = 8192


@dataclass(frozen=True)
class FrameSyncMatch:
    bit_offset: int
    hamming_distance: int


def bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError(f"le nombre de bits doit etre multiple de 8, recu {len(bits)}")
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | (bit & 1)
        out.append(byte)
    return bytes(out)


def hamming_distance_bits(a: list[int], b: list[int]) -> int:
    if len(a) != len(b):
        raise ValueError("les deux sequences de bits doivent avoir la meme longueur")
    return sum(1 for x, y in zip(a, b) if x != y)


def find_sync_markers(
    bitstream: list[int],
    marker: bytes = DEFAULT_CCSDS_ASM,
    max_hamming_distance: int = 2,
) -> list[FrameSyncMatch]:
    if not bitstream:
        raise ValueError("bitstream ne doit pas etre vide")
    if max_hamming_distance < 0:
        raise ValueError(f"max_hamming_distance doit etre >= 0, recu {max_hamming_distance}")

    marker_bits = bytes_to_bits(marker)
    marker_len = len(marker_bits)

    matches: list[FrameSyncMatch] = []
    for offset in range(0, len(bitstream) - marker_len + 1):
        window = bitstream[offset : offset + marker_len]
        distance = hamming_distance_bits(window, marker_bits)
        if distance <= max_hamming_distance:
            matches.append(FrameSyncMatch(bit_offset=offset, hamming_distance=distance))
    return matches


def extract_frames(
    bitstream: list[int],
    frame_length_bits: int,
    marker: bytes = DEFAULT_CCSDS_ASM,
    max_hamming_distance: int = 2,
) -> list[bytes]:
    if frame_length_bits <= 0:
        raise ValueError(f"frame_length_bits doit etre positif, recu {frame_length_bits}")
    if frame_length_bits % 8 != 0:
        raise ValueError("frame_length_bits doit etre multiple de 8")

    marker_bits = bytes_to_bits(marker)
    marker_len = len(marker_bits)

    frames: list[bytes] = []
    offset = 0
    n = len(bitstream)
    while offset + frame_length_bits <= n:
        window = bitstream[offset : offset + marker_len]
        if len(window) == marker_len and hamming_distance_bits(window, marker_bits) <= max_hamming_distance:
            frame_bits = bitstream[offset : offset + frame_length_bits]
            frames.append(bits_to_bytes(frame_bits))
            offset += frame_length_bits
        else:
            offset += 1
    return frames
