import pytest

from satrx.decode.derandomize import derandomize, generate_pn_sequence

# 16 premiers octets confirmes contre le decodeur LRPT open source artlav/meteor_decoder
# (recherche du 16/08/2026) - fixture de reference reelle, pas une valeur inventee.
_REFERENCE_PN_PREFIX = bytes(
    [0xFF, 0x48, 0x0E, 0xC0, 0x9A, 0x0D, 0x70, 0xBC, 0x8E, 0x2C, 0x93, 0xAD, 0xA7, 0xB7, 0x46, 0xCE]
)


class TestGeneratePnSequence:

    def test_nominal_case_matches_confirmed_reference(self):
        sequence = generate_pn_sequence()

        assert sequence[:16] == _REFERENCE_PN_PREFIX

    def test_nominal_case_length_and_uniqueness(self):
        sequence = generate_pn_sequence()

        assert len(sequence) == 255
        assert len(set(sequence)) == 255

    def test_edge_case_invalid_length(self):
        with pytest.raises(ValueError):
            generate_pn_sequence(0)

    def test_interop_shorter_length_is_prefix_of_full_sequence(self):
        full = generate_pn_sequence()
        short = generate_pn_sequence(16)

        assert short == full[:16]


class TestDerandomize:

    def test_nominal_case_xor_is_self_inverse(self):
        data = bytes(range(50))

        randomized = derandomize(data)
        recovered = derandomize(randomized)

        assert recovered == data

    def test_nominal_case_first_bytes_match_reference_sequence(self):
        data = bytes([0] * 16)

        result = derandomize(data)

        assert result == _REFERENCE_PN_PREFIX

    def test_edge_case_empty_data(self):
        with pytest.raises(ValueError):
            derandomize(b"")

    def test_interop_wraps_around_at_255_bytes(self):
        data = bytes([0] * 300)

        result = derandomize(data)

        assert result[:255] == generate_pn_sequence()
        assert result[255:260] == generate_pn_sequence()[:5]
