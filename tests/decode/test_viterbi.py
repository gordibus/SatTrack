import pytest

from satrx.decode.viterbi import convolutional_encode, viterbi_decode


class TestConvolutionalEncode:

    def test_nominal_case_rate_one_half_output_length(self):
        bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1]

        encoded = convolutional_encode(bits)

        assert len(encoded) == len(bits) * 2
        assert all(b in (0, 1) for b in encoded)

    def test_edge_case_invalid_bit_value(self):
        with pytest.raises(ValueError):
            convolutional_encode([0, 1, 2])

    def test_edge_case_invalid_constraint_length(self):
        with pytest.raises(ValueError):
            convolutional_encode([0, 1], constraint_length=1)


class TestViterbiDecode:

    def test_nominal_case_no_errors_roundtrip(self):
        bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0, 1]

        encoded = convolutional_encode(bits)
        decoded = viterbi_decode(encoded)

        assert decoded == bits

    def test_nominal_case_corrects_scattered_bit_errors(self):
        bits = [1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1]
        encoded = convolutional_encode(bits)

        noisy = list(encoded)
        noisy[3] ^= 1
        noisy[14] ^= 1
        noisy[27] ^= 1

        decoded = viterbi_decode(noisy)

        assert decoded == bits

    def test_edge_case_empty_input(self):
        with pytest.raises(ValueError):
            viterbi_decode([])

    def test_edge_case_length_not_multiple_of_rate(self):
        with pytest.raises(ValueError):
            viterbi_decode([0, 1, 1])

    def test_interop_convolutional_encode_output_is_directly_decodable(self):
        bits = [0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1, 0]

        encoded = convolutional_encode(bits, polynomials=(0o5, 0o7), constraint_length=3)
        decoded = viterbi_decode(encoded, polynomials=(0o5, 0o7), constraint_length=3)

        assert decoded == bits
