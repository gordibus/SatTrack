from __future__ import annotations

# Decodage entropique JPEG baseline (Huffman canonique + codage categorie/magnitude des
# coefficients DC/AC, run-length ZRL/EOB) : algorithme standardise par ITU T.81, donc
# generique independamment des tables reellement utilisees. Les tables elles-memes sont
# des parametres de build_huffman_*_table, pas des constantes figees ici.

ZRL = 0xF0  # run-length de 16 zeros (symbole AC particulier)
EOB = 0x00  # end-of-block (run=0, size=0)

# Tables de Huffman standard JPEG baseline (luminance, ITU T.81 Annexe K.3) : confirmees
# comme utilisees telles quelles par l'encodeur LRPT Meteor-M (recherche du 16/08/2026,
# recoupee entre le decodeur LRPT open source artlav/meteor_decoder - fichier huffman.pas -
# et l'implementation standard OpenJDK JPEGHuffmanTable.StdDCLuminance/StdACLuminance,
# qui donnent les memes valeurs).
STANDARD_DC_LUMINANCE_BITS = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
STANDARD_DC_LUMINANCE_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

STANDARD_AC_LUMINANCE_BITS = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D]
STANDARD_AC_LUMINANCE_VALUES = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12,
    0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07,
    0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0,
    0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16,
    0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
    0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
    0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
    0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98,
    0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
    0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
    0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5,
    0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4,
    0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA,
    0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8,
    0xF9, 0xFA,
]


class BitReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos = 0
        self._bit_pos = 0

    def read_bit(self) -> int:
        if self._byte_pos >= len(self._data):
            raise ValueError("fin du flux de bits atteinte de maniere inattendue")
        byte = self._data[self._byte_pos]
        bit = (byte >> (7 - self._bit_pos)) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bit_pos = 0
            self._byte_pos += 1
        return bit

    def at_end(self) -> bool:
        return self._byte_pos >= len(self._data)


class BitWriter:
    def __init__(self) -> None:
        self._bytes = bytearray()
        self._current = 0
        self._bit_pos = 0

    def write_bit(self, bit: int) -> None:
        self._current = (self._current << 1) | (bit & 1)
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bytes.append(self._current)
            self._current = 0
            self._bit_pos = 0

    def write_bits(self, value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def getvalue(self) -> bytes:
        if self._bit_pos == 0:
            return bytes(self._bytes)
        padded = self._current << (8 - self._bit_pos)
        return bytes(self._bytes) + bytes([padded])


def build_huffman_decode_table(bit_counts: list[int], symbols: list[int]) -> dict[tuple[int, int], int]:
    if len(bit_counts) != 16:
        raise ValueError(f"bit_counts doit contenir exactement 16 valeurs, recu {len(bit_counts)}")
    if sum(bit_counts) != len(symbols):
        raise ValueError("la somme de bit_counts doit correspondre au nombre de symboles")

    table: dict[tuple[int, int], int] = {}
    code = 0
    symbol_index = 0
    for length in range(1, 17):
        count = bit_counts[length - 1]
        if code + count > (1 << length):
            raise ValueError(
                f"table de Huffman invalide : trop de symboles de longueur {length} "
                "(viole l'inegalite de Kraft)"
            )
        for _ in range(count):
            table[(length, code)] = symbols[symbol_index]
            symbol_index += 1
            code += 1
        code <<= 1
    return table


def build_huffman_encode_table(bit_counts: list[int], symbols: list[int]) -> dict[int, tuple[int, int]]:
    decode_table = build_huffman_decode_table(bit_counts, symbols)
    return {symbol: (length, code) for (length, code), symbol in decode_table.items()}


def standard_dc_luminance_decode_table() -> dict[tuple[int, int], int]:
    return build_huffman_decode_table(STANDARD_DC_LUMINANCE_BITS, STANDARD_DC_LUMINANCE_VALUES)


def standard_dc_luminance_encode_table() -> dict[int, tuple[int, int]]:
    return build_huffman_encode_table(STANDARD_DC_LUMINANCE_BITS, STANDARD_DC_LUMINANCE_VALUES)


def standard_ac_luminance_decode_table() -> dict[tuple[int, int], int]:
    return build_huffman_decode_table(STANDARD_AC_LUMINANCE_BITS, STANDARD_AC_LUMINANCE_VALUES)


def standard_ac_luminance_encode_table() -> dict[int, tuple[int, int]]:
    return build_huffman_encode_table(STANDARD_AC_LUMINANCE_BITS, STANDARD_AC_LUMINANCE_VALUES)


def decode_huffman_symbol(reader: BitReader, table: dict[tuple[int, int], int]) -> int:
    code = 0
    for length in range(1, 17):
        code = (code << 1) | reader.read_bit()
        if (length, code) in table:
            return table[(length, code)]
    raise ValueError("code Huffman invalide : aucun symbole trouve apres 16 bits")


def encode_huffman_symbol(writer: BitWriter, table: dict[int, tuple[int, int]], symbol: int) -> None:
    if symbol not in table:
        raise ValueError(f"symbole {symbol} absent de la table de Huffman")
    length, code = table[symbol]
    writer.write_bits(code, length)


def value_to_category(value: int) -> tuple[int, int]:
    if value == 0:
        return 0, 0
    magnitude = abs(value)
    category = magnitude.bit_length()
    bits = value if value > 0 else value + (1 << category) - 1
    return category, bits


def receive_extend(reader: BitReader, category: int) -> int:
    if category == 0:
        return 0
    value = 0
    for _ in range(category):
        value = (value << 1) | reader.read_bit()
    if value < (1 << (category - 1)):
        value -= (1 << category) - 1
    return value


def decode_block(
    reader: BitReader,
    dc_table: dict[tuple[int, int], int],
    ac_table: dict[tuple[int, int], int],
    prev_dc: int,
) -> tuple[list[int], int]:
    dc_category = decode_huffman_symbol(reader, dc_table)
    dc_diff = receive_extend(reader, dc_category)
    dc_value = prev_dc + dc_diff

    coeffs = [0] * 64
    coeffs[0] = dc_value

    k = 1
    while k < 64:
        run_size = decode_huffman_symbol(reader, ac_table)
        run = run_size >> 4
        size = run_size & 0x0F

        if size == 0:
            if run == 15:
                k += 16
                continue
            break  # EOB

        k += run
        if k >= 64:
            raise ValueError("depassement de bloc pendant le decodage AC : flux incoherent")
        coeffs[k] = receive_extend(reader, size)
        k += 1

    return coeffs, dc_value


def encode_block(
    writer: BitWriter,
    dc_table: dict[int, tuple[int, int]],
    ac_table: dict[int, tuple[int, int]],
    coeffs: list[int],
    prev_dc: int,
) -> int:
    if len(coeffs) != 64:
        raise ValueError(f"coeffs doit contenir 64 valeurs, recu {len(coeffs)}")

    dc_value = coeffs[0]
    dc_diff = dc_value - prev_dc
    dc_category, dc_bits = value_to_category(dc_diff)
    encode_huffman_symbol(writer, dc_table, dc_category)
    writer.write_bits(dc_bits, dc_category)

    last_nonzero = 0
    for k in range(63, 0, -1):
        if coeffs[k] != 0:
            last_nonzero = k
            break

    k = 1
    run = 0
    while k <= last_nonzero:
        if coeffs[k] == 0:
            run += 1
            if run == 16:
                encode_huffman_symbol(writer, ac_table, ZRL)
                run = 0
            k += 1
            continue
        category, bits = value_to_category(coeffs[k])
        encode_huffman_symbol(writer, ac_table, (run << 4) | category)
        writer.write_bits(bits, category)
        run = 0
        k += 1

    if last_nonzero < 63:
        encode_huffman_symbol(writer, ac_table, EOB)

    return dc_value
