from __future__ import annotations

import pytest

from satrx.decode.nrzm import nrzm_decode, nrzm_encode


class TestNrzmDecode:

    def test_nominal_all_ones_no_transition(self) -> None:
        # Un flux de '1' NRZ-M encode represente des bits SANS transition
        # (data[i]=0 => pas de changement => tous les bits encodes restent 1).
        # Decode : decoded[0]=1, puis decoded[i] = bits[i] XOR bits[i-1] = 1 XOR 1 = 0
        # => [1, 0, 0, 0, 0, 0, 0, 0]
        encoded = [1, 1, 1, 1, 1, 1, 1, 1]
        decoded = nrzm_decode(encoded)
        assert decoded == [1, 0, 0, 0, 0, 0, 0, 0]

    def test_nominal_alternating_produces_all_ones(self) -> None:
        # Un flux alternant [1,0,1,0,...] = nrzm_encode([1,1,1,...])
        # Decode : chaque XOR de bits adjacents differents = 1
        # decoded[0]=1, decoded[i] = 0 XOR 1 = 1 ou 1 XOR 0 = 1
        encoded = [1, 0, 1, 0, 1, 0, 1, 0]
        decoded = nrzm_decode(encoded)
        assert decoded == [1, 1, 1, 1, 1, 1, 1, 1]

    def test_nominal_all_zeros_constant(self) -> None:
        # Un flux de '0' encode signifie aucune transition.
        # Decode : 0 XOR 0 = 0 partout (premier bit = 0).
        encoded = [0, 0, 0, 0, 0, 0, 0, 0]
        decoded = nrzm_decode(encoded)
        assert decoded == [0, 0, 0, 0, 0, 0, 0, 0]

    def test_roundtrip_encode_decode(self) -> None:
        # nrzm_decode(nrzm_encode(x)) == [x[0]] + x[1:]  (premier bit ambigu mais stable)
        original = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0]
        encoded = nrzm_encode(original)
        decoded = nrzm_decode(encoded)
        # Les bits 1..N sont identiques a l'original, seul le bit 0 est ambigu
        assert decoded[1:] == original[1:]

    def test_roundtrip_full_reversibility(self) -> None:
        # Si on connait le premier bit encode, le decodage est exact.
        # Ici on cree un flux qui commence par 0 et verifie la reconstruction exacte.
        original = [0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0]
        encoded = nrzm_encode(original)
        decoded = nrzm_decode(encoded)
        assert decoded == original

    def test_single_transition_bit(self) -> None:
        # Un seul bit '1' isole dans le flux produit une transition unique.
        encoded = [0, 0, 0, 1, 0, 0, 0]
        # decoded[3] = 1 XOR 0 = 1, decoded[4] = 0 XOR 1 = 1, decoded[5] = 0 XOR 0 = 0
        expected = [0, 0, 0, 1, 1, 0, 0]
        assert nrzm_decode(encoded) == expected

    def test_preserves_length(self) -> None:
        bits = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        assert len(nrzm_decode(bits)) == len(bits)

    def test_empty_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            nrzm_decode([])

    def test_single_bit_returns_same(self) -> None:
        assert nrzm_decode([0]) == [0]
        assert nrzm_decode([1]) == [1]

    def test_interop_with_frame_sync_asm(self) -> None:
        """Apres NRZ-M decode, l'ASM 0x1ACFFC1D doit apparaitre dans le flux.

        Ce test cree un mini-flux encode NRZ-M contenant l'ASM et verifie que
        le decodage retrouve bien le motif ASM a la bonne position.
        """
        from satrx.decode.frame_sync import bytes_to_bits, find_sync_markers, DEFAULT_CCSDS_ASM

        asm_bits = bytes_to_bits(DEFAULT_CCSDS_ASM)  # 32 bits de 0x1ACFFC1D

        # Simuler un flux : padding + ASM + padding
        padding_before = [0] * 16
        payload = [0] * 64
        raw_data_bits = padding_before + asm_bits + payload

        # Encoder en NRZ-M (comme l'emetteur le ferait)
        encoded_bits = nrzm_encode(raw_data_bits)

        # Decoder (comme le recepteur doit le faire)
        decoded_bits = nrzm_decode(encoded_bits)

        # L'ASM doit etre retrouve a la position 16 (apres le padding)
        matches = find_sync_markers(decoded_bits, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=0)
        positions = [m.bit_offset for m in matches]
        assert 16 in positions, (
            f"ASM non trouve a la position 16 apres NRZ-M decode. Positions trouvees : {positions}"
        )


class TestNrzmEncode:

    def test_empty_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            nrzm_encode([])

    def test_encode_all_zeros_stays_zero(self) -> None:
        # data[i]=0 => pas de transition => encoded[i] = encoded[i-1]
        data = [0, 0, 0, 0, 0, 0, 0, 0]
        assert nrzm_encode(data) == [0, 0, 0, 0, 0, 0, 0, 0]

    def test_encode_all_ones_alternates(self) -> None:
        # data[i]=1 => transition => encoded[i] = 1 - encoded[i-1]
        data = [1, 1, 1, 1, 1, 1, 1, 1]
        # Commence a 1, puis alterne
        assert nrzm_encode(data) == [1, 0, 1, 0, 1, 0, 1, 0]
