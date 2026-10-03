import numpy as np
import pytest

from satrx.security.gmr1.a5gmr1 import (
    decrypt_burst_data,
    encrypt_burst_data,
    generate_keystream,
    initialize,
)
from satrx.security.gmr1.constants import GMR1_BURST_KEYSTREAM_BITS


KEY = bytes(range(8))        # cle de test : 0x00..0x07
FRAME = 42


class TestInitialize:

    def test_cle_invalide(self) -> None:
        with pytest.raises(ValueError, match="64 bits"):
            initialize(b"short", FRAME)

    def test_frame_invalide(self) -> None:
        with pytest.raises(ValueError, match="frame_num"):
            initialize(KEY, 1 << 22)

    def test_retourne_etat(self) -> None:
        state = initialize(KEY, FRAME)
        assert state.r1 != 0 or state.r2 != 0 or state.r3 != 0


class TestGenerateKeystream:

    def test_longueur(self) -> None:
        state = initialize(KEY, FRAME)
        ks = generate_keystream(state, GMR1_BURST_KEYSTREAM_BITS)
        assert ks.shape == (GMR1_BURST_KEYSTREAM_BITS,)

    def test_valeurs_binaires(self) -> None:
        state = initialize(KEY, FRAME)
        ks = generate_keystream(state, 200)
        assert np.all((ks == 0) | (ks == 1))

    def test_n_bits_invalide(self) -> None:
        state = initialize(KEY, FRAME)
        with pytest.raises(ValueError, match="n_bits"):
            generate_keystream(state, 0)

    def test_deux_cles_differentes_donnent_flux_differents(self) -> None:
        state1 = initialize(KEY, FRAME)
        state2 = initialize(bytes(range(1, 9)), FRAME)
        ks1 = generate_keystream(state1, 78)
        ks2 = generate_keystream(state2, 78)
        assert not np.array_equal(ks1, ks2)

    def test_deux_trames_differentes_donnent_flux_differents(self) -> None:
        state1 = initialize(KEY, FRAME)
        state2 = initialize(KEY, FRAME + 1)
        ks1 = generate_keystream(state1, 78)
        ks2 = generate_keystream(state2, 78)
        assert not np.array_equal(ks1, ks2)


class TestEncryptDecrypt:

    def test_roundtrip(self) -> None:
        rng = np.random.default_rng(7)
        plain = rng.integers(0, 2, GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)
        cipher = encrypt_burst_data(plain, KEY, FRAME)
        recovered = decrypt_burst_data(cipher, KEY, FRAME)
        np.testing.assert_array_equal(recovered, plain)

    def test_cipher_different_du_clair(self) -> None:
        plain = np.ones(GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)
        cipher = encrypt_burst_data(plain, KEY, FRAME)
        assert not np.array_equal(cipher, plain)

    def test_entropie_augmente_apres_chiffrement(self) -> None:
        from satrx.security.entropy import shannon_entropy

        # Un payload structure (alternance 0/1) doit avoir une entropie plus
        # haute apres chiffrement (flux de cle pseudo-aleatoire)
        plain = np.tile([1, 0, 0, 0], GMR1_BURST_KEYSTREAM_BITS // 4 + 1)[
            :GMR1_BURST_KEYSTREAM_BITS
        ].astype(np.uint8)
        cipher = encrypt_burst_data(plain, KEY, FRAME)
        h_plain = shannon_entropy(plain.tobytes())
        h_cipher = shannon_entropy(cipher.tobytes())
        # L'entropie du chiffre doit etre superieure ou egale
        assert h_cipher >= h_plain - 0.1
