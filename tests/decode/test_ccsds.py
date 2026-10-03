import pytest

from satrx.decode.ccsds import (
    SEQUENCE_FLAG_CONTINUATION,
    SEQUENCE_FLAG_FIRST,
    SEQUENCE_FLAG_LAST,
    SEQUENCE_FLAG_UNSEGMENTED,
    demux_by_apid,
    parse_all_packets,
    parse_packet,
    parse_primary_header,
    reassemble_apid_stream,
)


def _build_packet(
    apid: int,
    sequence_flags: int,
    sequence_count: int,
    payload: bytes,
    version: int = 0,
    packet_type: int = 0,
    secondary_header_flag: bool = False,
) -> bytes:
    b0 = (
        (version & 0b111) << 5
        | (packet_type & 0b1) << 4
        | (int(secondary_header_flag) & 0b1) << 3
        | ((apid >> 8) & 0b111)
    )
    b1 = apid & 0xFF
    b2 = (sequence_flags & 0b11) << 6 | ((sequence_count >> 8) & 0b111111)
    b3 = sequence_count & 0xFF
    length_field = len(payload) - 1
    b4 = (length_field >> 8) & 0xFF
    b5 = length_field & 0xFF
    return bytes([b0, b1, b2, b3, b4, b5]) + payload


class TestParsePrimaryHeader:

    def test_nominal_case(self):
        packet_bytes = _build_packet(
            apid=100, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=5, payload=b"hello!"
        )

        header = parse_primary_header(packet_bytes)

        assert header.apid == 100
        assert header.sequence_flags == SEQUENCE_FLAG_UNSEGMENTED
        assert header.sequence_count == 5
        assert header.data_length == 6

    def test_edge_case_truncated_header(self):
        with pytest.raises(ValueError):
            parse_primary_header(b"\x00\x01\x02")


class TestParsePacket:

    def test_nominal_case(self):
        packet_bytes = _build_packet(
            apid=64, sequence_flags=SEQUENCE_FLAG_FIRST, sequence_count=1, payload=b"IMGDATA"
        )

        packet, remainder = parse_packet(packet_bytes)

        assert packet.header.apid == 64
        assert packet.data == b"IMGDATA"
        assert remainder == b""

    def test_edge_case_insufficient_payload(self):
        packet_bytes = _build_packet(
            apid=64, sequence_flags=SEQUENCE_FLAG_LAST, sequence_count=1, payload=b"12345"
        )
        truncated = packet_bytes[:-2]

        with pytest.raises(ValueError):
            parse_packet(truncated)

    def test_interop_with_parse_primary_header(self):
        packet_bytes = _build_packet(
            apid=65, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=3, payload=b"XYZ"
        )

        header = parse_primary_header(packet_bytes)
        packet, _ = parse_packet(packet_bytes)

        assert packet.header == header


class TestParseAllPacketsAndDemux:

    def test_nominal_case(self):
        stream = (
            _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=0, payload=b"AA")
            + _build_packet(apid=65, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=0, payload=b"BBB")
            + _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=1, payload=b"CC")
        )

        packets = parse_all_packets(stream)
        by_apid = demux_by_apid(packets)

        assert len(packets) == 3
        assert [p.data for p in by_apid[64]] == [b"AA", b"CC"]
        assert [p.data for p in by_apid[65]] == [b"BBB"]

    def test_edge_case_trailing_garbage_stops_parsing(self):
        stream = (
            _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=0, payload=b"AA")
            + b"\x00\x01"
        )

        packets = parse_all_packets(stream)

        assert len(packets) == 1
        assert packets[0].data == b"AA"


class TestReassembleApidStream:

    def test_nominal_case_out_of_order_input(self):
        first = _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_FIRST, sequence_count=0, payload=b"AB")
        middle = _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_CONTINUATION, sequence_count=1, payload=b"CD")
        last = _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_LAST, sequence_count=2, payload=b"EF")
        packets = [parse_packet(last)[0], parse_packet(first)[0], parse_packet(middle)[0]]

        reassembled = reassemble_apid_stream(packets)

        assert reassembled == b"ABCDEF"

    def test_edge_case_empty_list(self):
        with pytest.raises(ValueError):
            reassemble_apid_stream([])

    def test_edge_case_mixed_apids(self):
        packet_a = parse_packet(
            _build_packet(apid=64, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=0, payload=b"A")
        )[0]
        packet_b = parse_packet(
            _build_packet(apid=65, sequence_flags=SEQUENCE_FLAG_UNSEGMENTED, sequence_count=0, payload=b"B")
        )[0]

        with pytest.raises(ValueError):
            reassemble_apid_stream([packet_a, packet_b])
