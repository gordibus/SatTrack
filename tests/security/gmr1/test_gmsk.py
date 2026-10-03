import numpy as np
import pytest

from satrx.security.gmr1.gmsk import gaussian_freq_pulse, gmsk_modulate, to_cs8


class TestGaussianFreqPulse:

    def test_longueur(self) -> None:
        h = gaussian_freq_pulse(bt=0.3, sps=8, n_sym=5)
        assert h.shape == (5 * 8 + 1,)

    def test_somme_egale_un(self) -> None:
        h = gaussian_freq_pulse(bt=0.3, sps=8)
        assert abs(h.sum() - 1.0) < 1e-9

    def test_bt_invalide(self) -> None:
        with pytest.raises(ValueError, match="bt"):
            gaussian_freq_pulse(bt=0.0, sps=8)

    def test_sps_invalide(self) -> None:
        with pytest.raises(ValueError, match="sps"):
            gaussian_freq_pulse(bt=0.3, sps=0)


class TestGmskModulate:

    def test_longueur_sortie(self) -> None:
        bits = np.zeros(10, dtype=np.uint8)
        iq = gmsk_modulate(bits, sps=4)
        assert len(iq) > len(bits) * 4  # filtre ajoute de la longueur

    def test_module_unitaire(self) -> None:
        bits = np.array([1, 0, 1, 1, 0], dtype=np.uint8)
        iq = gmsk_modulate(bits, sps=8)
        np.testing.assert_allclose(np.abs(iq), 1.0, atol=1e-10)

    def test_changement_de_phase_par_bit(self) -> None:
        # N bits tous a 1 : phase finale ≈ N * pi/2 (GMSK h=0.5)
        n_bits = 20
        bits = np.ones(n_bits, dtype=np.uint8)
        iq = gmsk_modulate(bits, sps=16, bt=0.3)
        phase = np.unwrap(np.angle(iq))
        expected = n_bits * np.pi / 2
        # Tolerance large : bord de filtre et delai de groupe gaussien
        assert abs(phase[-1] - expected) < 1.0

    def test_bits_invalides(self) -> None:
        with pytest.raises(ValueError, match="0/1"):
            gmsk_modulate(np.array([0, 2, 1], dtype=np.uint8))

    def test_sps_invalide(self) -> None:
        with pytest.raises(ValueError, match="sps"):
            gmsk_modulate(np.zeros(4, dtype=np.uint8), sps=0)

    def test_interop_avec_burst(self) -> None:
        from satrx.security.gmr1.burst import encode_normal_burst
        from satrx.security.gmr1.constants import GMR1_NB_DATA, GMR1_NB_ACTIVE_BITS

        data = np.ones(2 * GMR1_NB_DATA, dtype=np.uint8)
        b = encode_normal_burst(data)
        iq = gmsk_modulate(b, sps=8)
        # Le signal est bien complexe et de longueur coherente avec 148 bits × 8 sps
        assert iq.dtype == np.complex128
        assert len(iq) >= GMR1_NB_ACTIVE_BITS * 8


class TestToCs8:

    def test_longueur(self) -> None:
        iq = np.ones(10, dtype=np.complex128)
        cs8 = to_cs8(iq)
        assert len(cs8) == 20

    def test_format_interleave(self) -> None:
        iq = np.array([1 + 2j, 3 + 4j])
        cs8 = to_cs8(iq, amplitude=1.0)
        assert cs8[0] == 1  # I0
        assert cs8[1] == 2  # Q0
        assert cs8[2] == 3  # I1
        assert cs8[3] == 4  # Q1

    def test_saturation(self) -> None:
        iq = np.array([1000 + 1000j])
        cs8 = to_cs8(iq, amplitude=127.0)
        assert cs8[0] == 127
        assert cs8[1] == 127

    def test_amplitude_invalide(self) -> None:
        with pytest.raises(ValueError, match="amplitude"):
            to_cs8(np.ones(4), amplitude=0.0)
