from satrx.decode.derandomize import derandomize
from satrx.decode.frame_sync import (
    DEFAULT_CCSDS_ASM,
    bits_to_bytes,
    bytes_to_bits,
    find_sync_markers,
)
from satrx.decode.reed_solomon import rs_decode, rs_encode
from satrx.decode.viterbi import convolutional_encode, viterbi_decode


class TestFrameSyncToViterbiPipeline:

    def test_asm_detection_then_fec_recovery_despite_channel_errors(self):
        payload_bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0]
        encoded_payload = convolutional_encode(payload_bits)

        asm_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)
        bitstream = asm_bits + encoded_payload

        noisy = list(bitstream)
        noisy[len(asm_bits) + 5] ^= 1
        noisy[len(asm_bits) + 20] ^= 1

        matches = find_sync_markers(noisy, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)
        assert matches and matches[0].bit_offset == 0

        recovered_encoded = noisy[len(asm_bits) :]
        decoded = viterbi_decode(recovered_encoded)

        assert decoded == payload_bits


class TestViterbiToReedSolomonPipeline:

    def test_rs_payload_survives_viterbi_encode_channel_noise_and_decode(self):
        message = list(range(50))
        rs_encoded = rs_encode(message, nsym=16)

        bits = bytes_to_bits(bytes(rs_encoded))
        viterbi_encoded = convolutional_encode(bits)

        noisy = list(viterbi_encoded)
        for offset in (3, 47, 120, 250):
            noisy[offset] ^= 1

        recovered_bits = viterbi_decode(noisy)
        assert recovered_bits == bits

        recovered_bytes = bits_to_bytes(recovered_bits)
        rs_decoded = rs_decode(list(recovered_bytes), nsym=16)

        assert rs_decoded == message


class TestFullCaduPipeline:

    def test_asm_viterbi_derandomize_reed_solomon_full_chain(self):
        # reproduit l'ordre reel d'un CADU Meteor-M/CCSDS : ASM en clair, puis
        # RS -> randomisation -> codage convolutionnel cote emission ; a la reception :
        # synchro ASM -> Viterbi -> derandomisation -> Reed-Solomon.
        message = list(range(50))
        rs_encoded = bytes(rs_encode(message, nsym=16))

        randomized = derandomize(rs_encoded)
        bits = bytes_to_bits(randomized)
        viterbi_encoded = convolutional_encode(bits)

        asm_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)
        bitstream = asm_bits + viterbi_encoded

        noisy = list(bitstream)
        for offset in (len(asm_bits) + 10, len(asm_bits) + 200):
            noisy[offset] ^= 1

        matches = find_sync_markers(noisy, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)
        assert matches and matches[0].bit_offset == 0

        recovered_encoded = noisy[len(asm_bits) :]
        recovered_bits = viterbi_decode(recovered_encoded)
        recovered_randomized = bits_to_bytes(recovered_bits)

        recovered_rs_encoded = derandomize(recovered_randomized)
        rs_decoded = rs_decode(list(recovered_rs_encoded), nsym=16)

        assert rs_decoded == message
