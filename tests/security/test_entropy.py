import os

import pytest

from satrx.decode.ccsds import SEQUENCE_FLAG_UNSEGMENTED, CcsdsPacket, CcsdsPrimaryHeader
from satrx.security.entropy import analyze_packets_by_apid, classify_payload, shannon_entropy


def _packet(apid: int, data: bytes, sequence_count: int = 0) -> CcsdsPacket:
    header = CcsdsPrimaryHeader(
        version=0,
        packet_type=0,
        secondary_header_flag=False,
        apid=apid,
        sequence_flags=SEQUENCE_FLAG_UNSEGMENTED,
        sequence_count=sequence_count,
        data_length=len(data),
    )
    return CcsdsPacket(header=header, data=data)


class TestShannonEntropy:

    def test_nominal_case_constant_byte_has_zero_entropy(self):
        assert shannon_entropy(bytes([42] * 1000)) == pytest.approx(0.0)

    def test_nominal_case_uniform_random_has_high_entropy(self):
        data = os.urandom(4096)

        entropy = shannon_entropy(data)

        assert entropy > 7.5

    def test_edge_case_empty_data(self):
        with pytest.raises(ValueError):
            shannon_entropy(b"")


class TestClassifyPayload:

    def test_nominal_case_structured_text_is_clear(self):
        text = b"METEOR-M2 3 TELEMETRY " * 50

        assert classify_payload(text) == "probablement clair / structure"

    def test_nominal_case_random_bytes_is_encrypted(self):
        data = os.urandom(4096)

        assert classify_payload(data) == "probablement chiffre ou compresse"


class TestAnalyzePacketsByApid:

    def test_nominal_case_separates_clear_and_encrypted_apids(self):
        clear_data = b"TEMP=20C PRESSURE=1013HPA STATUS=OK " * 20
        encrypted_data = os.urandom(500)

        packets = [
            _packet(apid=64, data=clear_data, sequence_count=0),
            _packet(apid=65, data=encrypted_data, sequence_count=0),
        ]

        reports = analyze_packets_by_apid(packets)
        by_apid = {r.apid: r for r in reports}

        assert by_apid[64].classification == "probablement clair / structure"
        assert by_apid[65].classification == "probablement chiffre ou compresse"

    def test_edge_case_empty_packet_list(self):
        with pytest.raises(ValueError):
            analyze_packets_by_apid([])

    def test_interop_aggregates_multiple_packets_same_apid(self):
        packets = [
            _packet(apid=64, data=b"AAAA", sequence_count=0),
            _packet(apid=64, data=b"BBBB", sequence_count=1),
        ]

        reports = analyze_packets_by_apid(packets)

        assert len(reports) == 1
        assert reports[0].packet_count == 2
        assert reports[0].total_bytes == 8
