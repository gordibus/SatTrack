import json
from pathlib import Path

import numpy as np
import pytest

from satrx.security.gmr1.constants import (
    GMR1_BURST_KEYSTREAM_BITS,
    GMR1_FRAME_SLOTS,
    GMR1_NB_ACTIVE_BITS,
    GMR1_SYM_RATE,
)
from satrx.security.gmr1.signal_gen import generate_gmr1_signal, save_gmr1_iq

KEY = bytes(8)  # cle nulle : OK pour les tests synthetiques


class TestGenerateGmr1Signal:

    def test_longueur_approximative(self) -> None:
        sps = 4
        n_frames = 2
        iq = generate_gmr1_signal(n_frames=n_frames, key64=KEY, sps=sps)
        # Chaque frame = 8 slots × 148 bits × sps samples + marge filtre
        min_expected = n_frames * GMR1_FRAME_SLOTS * GMR1_NB_ACTIVE_BITS * sps
        assert len(iq) >= min_expected

    def test_dtype_complexe(self) -> None:
        iq = generate_gmr1_signal(n_frames=1, key64=KEY, sps=4)
        assert np.iscomplexobj(iq)

    def test_module_unitaire(self) -> None:
        iq = generate_gmr1_signal(n_frames=1, key64=KEY, sps=4, snr_db=None)
        np.testing.assert_allclose(np.abs(iq), 1.0, atol=1e-9)

    def test_bruit_ajoute(self) -> None:
        iq_clean = generate_gmr1_signal(
            n_frames=1, key64=KEY, sps=4, snr_db=None, rng=np.random.default_rng(0)
        )
        iq_noisy = generate_gmr1_signal(
            n_frames=1, key64=KEY, sps=4, snr_db=20.0, rng=np.random.default_rng(0)
        )
        # Signal bruite ne doit pas avoir un module strictement unitaire
        assert not np.allclose(np.abs(iq_noisy), 1.0)

    def test_n_frames_invalide(self) -> None:
        with pytest.raises(ValueError, match="n_frames"):
            generate_gmr1_signal(n_frames=0, key64=KEY, sps=4)

    def test_cle_invalide(self) -> None:
        with pytest.raises(ValueError, match="key64"):
            generate_gmr1_signal(n_frames=1, key64=b"short", sps=4)

    def test_sps_invalide(self) -> None:
        with pytest.raises(ValueError, match="sps"):
            generate_gmr1_signal(n_frames=1, key64=KEY, sps=1)

    def test_clair_vs_chiffre_different(self) -> None:
        rng = np.random.default_rng(99)
        iq_cipher = generate_gmr1_signal(
            n_frames=2, key64=KEY, sps=4, plaintext_frames=frozenset(), rng=rng
        )
        rng2 = np.random.default_rng(99)
        iq_plain = generate_gmr1_signal(
            n_frames=2, key64=KEY, sps=4, plaintext_frames=frozenset({0, 1}), rng=rng2
        )
        assert not np.allclose(iq_cipher, iq_plain), "signal clair == chiffre : inattendu"


class TestSaveGmr1Iq:

    def test_fichier_cs8_cree(self, tmp_path: Path) -> None:
        iq = generate_gmr1_signal(n_frames=1, key64=KEY, sps=4)
        out = tmp_path / "test.cs8"
        save_gmr1_iq(iq, out, sps=4)
        assert out.exists()

    def test_sidecar_json_cree(self, tmp_path: Path) -> None:
        iq = generate_gmr1_signal(n_frames=1, key64=KEY, sps=4)
        out = tmp_path / "test.cs8"
        save_gmr1_iq(iq, out, sps=4)
        meta_path = out.with_suffix(".cs8.json")
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["sample_rate_sps"] == GMR1_SYM_RATE * 4
        assert meta["format"] == "cs8"

    def test_taille_fichier_coherente(self, tmp_path: Path) -> None:
        iq = generate_gmr1_signal(n_frames=1, key64=KEY, sps=4)
        out = tmp_path / "test.cs8"
        save_gmr1_iq(iq, out, sps=4)
        # CS8 : 2 octets par echantillon (I + Q en int8)
        assert out.stat().st_size == 2 * len(iq)
