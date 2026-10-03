from __future__ import annotations

from dataclasses import dataclass

# Extraction generique de parametres de telemetrie depuis un buffer binaire (paquet CCSDS
# deja degroupe par decode/ccsds.py). Le plan de trame reel (offsets/longueurs/echelles des
# parametres Meteor-M) est specifique a la mission et n'est pas connu ici : ce module fournit
# le moteur d'extraction, les TelemetryParameterSpec concrets restent a fournir separement.


@dataclass(frozen=True)
class TelemetryParameterSpec:
    name: str
    bit_offset: int
    bit_length: int
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name ne doit pas etre vide")
        if self.bit_offset < 0:
            raise ValueError(f"bit_offset doit etre >= 0, recu {self.bit_offset}")
        if self.bit_length <= 0:
            raise ValueError(f"bit_length doit etre positif, recu {self.bit_length}")


def extract_raw_bits(data: bytes, bit_offset: int, bit_length: int) -> int:
    total_bits = len(data) * 8
    if bit_offset < 0:
        raise ValueError(f"bit_offset doit etre >= 0, recu {bit_offset}")
    if bit_length <= 0:
        raise ValueError(f"bit_length doit etre positif, recu {bit_length}")
    if bit_offset + bit_length > total_bits:
        raise ValueError(
            f"lecture hors limites : bit_offset={bit_offset} + bit_length={bit_length} "
            f"depasse les {total_bits} bits disponibles"
        )

    value = 0
    for i in range(bit_length):
        bit_index = bit_offset + i
        byte_index = bit_index // 8
        bit_in_byte = 7 - (bit_index % 8)
        bit = (data[byte_index] >> bit_in_byte) & 1
        value = (value << 1) | bit
    return value


def extract_parameter(data: bytes, spec: TelemetryParameterSpec) -> float:
    raw = extract_raw_bits(data, spec.bit_offset, spec.bit_length)
    return raw * spec.scale + spec.offset


def decode_telemetry_frame(data: bytes, specs: list[TelemetryParameterSpec]) -> dict[str, float]:
    if not specs:
        raise ValueError("specs ne doit pas etre vide")
    return {spec.name: extract_parameter(data, spec) for spec in specs}
