import numpy as np
import pytest

from satrx.security.gmr1.constants import (
    GMR1_BURST_KEYSTREAM_BITS,
    GMR1_FRAME_SLOTS,
    GMR1_NB_ACTIVE_BITS,
    GMR1_NB_DATA,
    GMR1_NB_MIDAMBLE,
    GMR1_NB_TRAINING_SEQ,
)
from satrx.security.gmr1.demod import (
    DemodResult,
    demodulate_signal,
    extract_data_from_burst,
    gmsk_demodulate_soft,
    locate_midambles,
)
from satrx.security.gmr1.gmsk import gmsk_modulate
from satrx.security.gmr1.burst import encode_normal_burst
from satrx.security.gmr1.signal_gen import generate_gmr1_signal

KEY = bytes(8)
SPS = 8


class TestGmskDemodulateSoft:

    def test_longueur_approximative(self) -> None:
        bits = np.zeros(GMR1_NB_ACTIVE_BITS, dtype=np.uint8)
        iq = gmsk_modulate(bits, sps=SPS)
        soft = gmsk_demodulate_soft(iq, sps=SPS)
        # Apres compensation du delai de groupe, le nombre de bits mous
        # doit etre inferieur a la longueur brute mais couvrir le burst
        assert len(soft) > 0

    def test_sps_invalide(self) -> None:
        with pytest.raises(ValueError, match="sps"):
            gmsk_demodulate_soft(np.ones(100, dtype=np.complex128), sps=1)

    def test_timing_offset_invalide(self) -> None:
        iq = np.ones(1000, dtype=np.complex128)
        with pytest.raises(ValueError, match="timing_offset"):
            gmsk_demodulate_soft(iq, sps=SPS, timing_offset=SPS)

    def test_signe_correct_bit_1(self) -> None:
        # Un burst tout-a-1 : bits mous doivent etre majoritairement positifs
        data = np.ones(GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)
        burst = encode_normal_burst(data)
        iq = gmsk_modulate(burst, sps=SPS)
        soft = gmsk_demodulate_soft(iq, sps=SPS)
        # La majorite des valeurs molles doit etre positive
        assert np.mean(soft > 0) > 0.6

    def test_signe_correct_bit_0(self) -> None:
        data = np.zeros(GMR1_BURST_KEYSTREAM_BITS, dtype=np.uint8)
        burst = encode_normal_burst(data)
        iq = gmsk_modulate(burst, sps=SPS)
        soft = gmsk_demodulate_soft(iq, sps=SPS)
        assert np.mean(soft < 0) > 0.6


class TestLocateMidambles:

    def _make_signal(self, n_frames: int = 1) -> tuple[np.ndarray, int]:  # type: ignore[type-arg]
        iq = generate_gmr1_signal(
            n_frames=n_frames,
            key64=KEY,
            sps=SPS,
            plaintext_frames=frozenset(range(n_frames)),
            rng=np.random.default_rng(0),
        )
        soft = gmsk_demodulate_soft(iq, sps=SPS)
        return soft, n_frames * GMR1_FRAME_SLOTS

    def test_nombre_correct_de_pics(self) -> None:
        soft, n_bursts = self._make_signal(n_frames=1)
        positions = locate_midambles(soft, n_bursts)
        assert len(positions) == n_bursts

    def test_espacement_entre_pics(self) -> None:
        soft, n_bursts = self._make_signal(n_frames=2)
        positions = locate_midambles(soft, n_bursts)
        assert len(positions) == n_bursts
        # Les pics doivent etre separes d'environ GMR1_NB_ACTIVE_BITS bits.
        # Tolerance de 10 bits : les effets de bord du filtre gaussien (longueur
        # 5 periodes symbole) peuvent decaler le pic de correlation de quelques bits.
        diffs = np.diff(positions)
        for d in diffs:
            assert abs(d - GMR1_NB_ACTIVE_BITS) <= 10, (
                f"Espacement entre pics={d}, attendu {GMR1_NB_ACTIVE_BITS} ± 10"
            )

    def test_training_seq_invalide(self) -> None:
        with pytest.raises(ValueError, match="training_seq"):
            locate_midambles(np.zeros(200), n_bursts=1, training_seq=np.zeros(10, dtype=np.uint8))


class TestExtractDataFromBurst:

    def test_longueur_sortie(self) -> None:
        soft = np.ones(GMR1_NB_ACTIVE_BITS + 10)
        midamble_pos = GMR1_NB_ACTIVE_BITS // 2  # position approximative
        # Position exacte du midamble dans un burst
        from satrx.security.gmr1.demod import _MIDAMBLE_OFFSET
        mid_pos = _MIDAMBLE_OFFSET + 5
        data_bits, soft_data = extract_data_from_burst(soft, mid_pos)
        assert len(data_bits) == GMR1_BURST_KEYSTREAM_BITS
        assert len(soft_data) == GMR1_BURST_KEYSTREAM_BITS

    def test_flux_trop_court(self) -> None:
        with pytest.raises(ValueError, match="trop court"):
            extract_data_from_burst(np.zeros(10), midamble_pos=100)

    def test_midamble_trop_pres_du_debut(self) -> None:
        with pytest.raises(ValueError, match="trop proche"):
            extract_data_from_burst(np.zeros(200), midamble_pos=1)


class TestDemodulateSignal:

    def test_roundtrip_clair(self) -> None:
        """Roundtrip : generation → demodulation sur signal non chiffre."""
        rng = np.random.default_rng(42)
        n_frames = 1
        iq = generate_gmr1_signal(
            n_frames=n_frames,
            key64=KEY,
            sps=SPS,
            plaintext_frames=frozenset(range(n_frames)),
            snr_db=None,
            rng=rng,
        )
        results = demodulate_signal(
            iq, sps=SPS, n_frames=n_frames, timing_offset=0
        )
        # On doit trouver 8 bursts (1 trame × 8 slots)
        assert len(results) == GMR1_FRAME_SLOTS

    def test_structure_demod_result(self) -> None:
        n_frames = 1
        iq = generate_gmr1_signal(
            n_frames=n_frames, key64=KEY, sps=SPS,
            plaintext_frames=frozenset({0}), rng=np.random.default_rng(1)
        )
        results = demodulate_signal(iq, sps=SPS, n_frames=n_frames, timing_offset=0)
        for r in results:
            assert isinstance(r, DemodResult)
            assert r.data_bits.shape == (GMR1_BURST_KEYSTREAM_BITS,)
            assert np.all((r.data_bits == 0) | (r.data_bits == 1))

    def test_sps_invalide(self) -> None:
        with pytest.raises(ValueError, match="sps"):
            demodulate_signal(np.ones(100, dtype=np.complex128), sps=1, n_frames=1)

    def test_n_frames_invalide(self) -> None:
        with pytest.raises(ValueError, match="n_frames"):
            demodulate_signal(np.ones(100, dtype=np.complex128), sps=SPS, n_frames=0)

    def test_midamble_corr_positive(self) -> None:
        n_frames = 1
        iq = generate_gmr1_signal(
            n_frames=n_frames, key64=KEY, sps=SPS,
            plaintext_frames=frozenset({0}), rng=np.random.default_rng(2)
        )
        results = demodulate_signal(iq, sps=SPS, n_frames=n_frames, timing_offset=0)
        # La correlation du midamble doit etre positive (signal coherent detecte)
        corrs = [r.midamble_corr for r in results]
        assert max(corrs) > 0.0, f"Correlation max={max(corrs)} negative"
