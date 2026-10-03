from __future__ import annotations

from dataclasses import dataclass

PRIMARY_HEADER_LENGTH_BYTES = 6

SEQUENCE_FLAG_CONTINUATION = 0b00
SEQUENCE_FLAG_FIRST = 0b01
SEQUENCE_FLAG_LAST = 0b10
SEQUENCE_FLAG_UNSEGMENTED = 0b11


@dataclass(frozen=True)
class CcsdsPrimaryHeader:
    version: int
    packet_type: int
    secondary_header_flag: bool
    apid: int
    sequence_flags: int
    sequence_count: int
    data_length: int


@dataclass(frozen=True)
class CcsdsPacket:
    header: CcsdsPrimaryHeader
    data: bytes


def parse_primary_header(data: bytes) -> CcsdsPrimaryHeader:
    if len(data) < PRIMARY_HEADER_LENGTH_BYTES:
        raise ValueError(
            f"en-tete CCSDS incomplet : {len(data)} octets fournis, "
            f"{PRIMARY_HEADER_LENGTH_BYTES} requis"
        )
    b0, b1, b2, b3, b4, b5 = data[:PRIMARY_HEADER_LENGTH_BYTES]

    return CcsdsPrimaryHeader(
        version=(b0 >> 5) & 0b111,
        packet_type=(b0 >> 4) & 0b1,
        secondary_header_flag=bool((b0 >> 3) & 0b1),
        apid=((b0 & 0b111) << 8) | b1,
        sequence_flags=(b2 >> 6) & 0b11,
        sequence_count=((b2 & 0b111111) << 8) | b3,
        data_length=((b4 << 8) | b5) + 1,
    )


def parse_packet(data: bytes) -> tuple[CcsdsPacket, bytes]:
    header = parse_primary_header(data)
    total_length = PRIMARY_HEADER_LENGTH_BYTES + header.data_length
    if len(data) < total_length:
        raise ValueError(
            f"donnees insuffisantes pour le paquet APID {header.apid} : "
            f"{len(data)} octets fournis, {total_length} requis"
        )
    packet_data = data[PRIMARY_HEADER_LENGTH_BYTES:total_length]
    remainder = data[total_length:]
    return CcsdsPacket(header=header, data=packet_data), remainder


def parse_all_packets(data: bytes) -> list[CcsdsPacket]:
    packets: list[CcsdsPacket] = []
    remaining = data
    while len(remaining) >= PRIMARY_HEADER_LENGTH_BYTES:
        header = parse_primary_header(remaining)
        total_length = PRIMARY_HEADER_LENGTH_BYTES + header.data_length
        if len(remaining) < total_length:
            break
        packet, remaining = parse_packet(remaining)
        packets.append(packet)
    return packets


def demux_by_apid(packets: list[CcsdsPacket]) -> dict[int, list[CcsdsPacket]]:
    by_apid: dict[int, list[CcsdsPacket]] = {}
    for packet in packets:
        by_apid.setdefault(packet.header.apid, []).append(packet)
    return by_apid


def reassemble_apid_stream(packets: list[CcsdsPacket]) -> bytes:
    if not packets:
        raise ValueError("packets ne doit pas etre vide")

    apid = packets[0].header.apid
    if any(p.header.apid != apid for p in packets):
        raise ValueError("tous les paquets doivent partager le meme APID pour etre reassembles")

    sorted_packets = sorted(packets, key=lambda p: p.header.sequence_count)
    return b"".join(p.data for p in sorted_packets)
