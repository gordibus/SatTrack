import numpy as np
import pytest

from satrx.security.gmr1.burst import (
    decode_burst_data,
    encode_normal_burst,
    generate_idle_burst,
)
from satrx.security.gmr1.constants import (
    GMR1_NB_ACTIVE_BITS,
    GMR1_NB_DATA,
    GMR1_NB_MIDAMBLE,
    GMR1_NB_TAIL,
    GMR1_NB_TRAINING_SEQ,
)


class TestEncodeNormalBurst:

    def test_longueur_burst(self) -> None:
        data = np.zeros(2 * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        assert b.shape == (GMR1_NB_ACTIVE_BITS,)

    def test_tail_bits_nuls(self) -> None:
        data = np.ones(2 * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        assert np.all(b[:GMR1_NB_TAIL] == 0), "tail debut non nul"
        assert np.all(b[-GMR1_NB_TAIL:] == 0), "tail fin non nul"

    def test_midamble_insere(self) -> None:
        data = np.zeros(2 * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        mid_start = GMR1_NB_TAIL + GMR1_NB_DATA
        mid_end = mid_start + GMR1_NB_MIDAMBLE
        np.testing.assert_array_equal(b[mid_start:mid_end], GMR1_NB_TRAINING_SEQ)

    def test_donnees_presentes(self) -> None:
        data = np.array([1, 0] * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        first = b[GMR1_NB_TAIL : GMR1_NB_TAIL + GMR1_NB_DATA]
        np.testing.assert_array_equal(first, data[:GMR1_NB_DATA])

    def test_mauvaise_longueur_data(self) -> None:
        with pytest.raises(ValueError, match="data_bits"):
            encode_normal_burst(np.zeros(10, dtype=np.uint8))

    def test_valeur_invalide_data(self) -> None:
        data = np.full(2 * GMR1_NB_DATA, 2, dtype=np.uint8)
        with pytest.raises(ValueError, match="0/1"):
            encode_normal_burst(data)

    def test_training_seq_personnalisee(self) -> None:
        data = np.zeros(2 * GMR1_NB_DATA, dtype=np.uint8)
        ts = np.ones(GMR1_NB_MIDAMBLE, dtype=np.uint8)
        b = encode_normal_burst(data, training_seq=ts)
        mid_start = GMR1_NB_TAIL + GMR1_NB_DATA
        np.testing.assert_array_equal(b[mid_start : mid_start + GMR1_NB_MIDAMBLE], ts)


class TestDecodeBurstData:

    def test_roundtrip(self) -> None:
        rng = np.random.default_rng(0)
        data = rng.integers(0, 2, size=2 * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        recovered = decode_burst_data(b)
        np.testing.assert_array_equal(recovered, data)

    def test_mauvaise_longueur(self) -> None:
        with pytest.raises(ValueError, match="148"):
            decode_burst_data(np.zeros(10, dtype=np.uint8))


class TestIdleBurst:

    def test_longueur(self) -> None:
        b = generate_idle_burst()
        assert b.shape == (GMR1_NB_ACTIVE_BITS,)

    def test_donnees_nulles(self) -> None:
        b = generate_idle_burst()
        data = decode_burst_data(b)
        assert np.all(data == 0)
