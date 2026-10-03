from __future__ import annotations

import numpy as np
import pytest

from satrx.demod.afsk import (
    BELL202,
    AfskParams,
    bits_to_bytes,
    decode_afsk_ascii,
    demodulate_afsk_bits,
)


def _make_afsk_signal(
    message: str,
    params: AfskParams = BELL202,
    sample_rate_hz: float = 48000.0,
    msb_first: bool = True,
) -> np.ndarray:
    """Genere un signal AFSK synthetique encodant message en ASCII."""
    bits: list[int] = []
    for ch in message:
        val = ord(ch)
        for j in range(8):
            if msb_first:
                bits.append((val >> (7 - j)) & 1)
            else:
                bits.append((val >> j) & 1)

    sym_len = int(round(sample_rate_hz / params.baud_rate))
    samples_list = []
    for bit in bits:
        freq = params.mark_hz if bit == 1 else params.space_hz
        t = np.arange(sym_len) / sample_rate_hz
        samples_list.append(np.sin(2 * np.pi * freq * t))
    return np.concatenate(samples_list)


class TestDemodulateAfskBits:

    def test_nominal_bell202_alternating(self) -> None:
        # Signal pur alternant mark/space : bits attendus 1, 0, 1, 0, ...
        sr = 48000.0
        sym = int(round(sr / BELL202.baud_rate))
        t_m = np.arange(sym) / sr
        t_s = np.arange(sym) / sr
        seg_m = np.sin(2 * np.pi * BELL202.mark_hz * t_m)
        seg_s = np.sin(2 * np.pi * BELL202.space_hz * t_s)
        sig = np.concatenate([seg_m, seg_s, seg_m, seg_s])
        bits = demodulate_afsk_bits(sig, sr, BELL202)
        # Les 4 premiers symboles doivent etre 1, 0, 1, 0
        assert bits[:4] == [1, 0, 1, 0]

    def test_nominal_ascii_htb_flag(self) -> None:
        # Reproduit exactement le challenge HTB : le flag doit etre retrouve
        sr = 48000.0
        flag = "HTB{AFSK_m0dul4710n_15_c00l!}"
        sig = _make_afsk_signal(flag, BELL202, sr)
        bits = demodulate_afsk_bits(sig, sr, BELL202)
        raw = bits_to_bytes(bits, msb_first=True)
        decoded = raw.decode("ascii", errors="replace")
        assert decoded == flag

    def test_nominal_custom_params(self) -> None:
        # Parametres differents de Bell 202 - le demodulateur doit s'adapter
        params = AfskParams(mark_hz=1800.0, space_hz=3000.0, baud_rate=600)
        sr = 48000.0
        msg = "OK"
        sig = _make_afsk_signal(msg, params, sr, msb_first=True)
        bits = demodulate_afsk_bits(sig, sr, params)
        raw = bits_to_bytes(bits, msb_first=True)
        assert raw.decode("ascii", errors="replace") == msg

    def test_edge_empty_samples(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            demodulate_afsk_bits(np.array([], dtype=np.float64), 48000.0)

    def test_edge_2d_input(self) -> None:
        with pytest.raises(ValueError, match="1D"):
            demodulate_afsk_bits(np.zeros((10, 2)), 48000.0)

    def test_edge_negative_samplerate(self) -> None:
        with pytest.raises(ValueError, match="positif"):
            demodulate_afsk_bits(np.ones(100), -1.0)


class TestAfskParams:

    def test_edge_identical_frequencies(self) -> None:
        with pytest.raises(ValueError, match="differents"):
            AfskParams(mark_hz=1200.0, space_hz=1200.0, baud_rate=1200)

    def test_edge_zero_baud(self) -> None:
        with pytest.raises(ValueError, match="positif"):
            AfskParams(mark_hz=1200.0, space_hz=2200.0, baud_rate=0)

    def test_edge_negative_freq(self) -> None:
        with pytest.raises(ValueError, match="positifs"):
            AfskParams(mark_hz=-100.0, space_hz=2200.0, baud_rate=1200)


class TestBitsToBytes:

    def test_nominal_msb_first(self) -> None:
        # 'H' = 0x48 = 0b01001000
        bits = [0, 1, 0, 0, 1, 0, 0, 0]
        assert bits_to_bytes(bits, msb_first=True) == b"H"

    def test_nominal_lsb_first(self) -> None:
        # 0x48 en LSB first : bits 0,0,0,1,0,0,1,0
        bits = [0, 0, 0, 1, 0, 0, 1, 0]
        assert bits_to_bytes(bits, msb_first=False) == b"H"

    def test_nominal_trailing_bits_ignored(self) -> None:
        # 9 bits : le 9e est ignore car il ne forme pas un octet complet
        bits = [0, 1, 0, 0, 1, 0, 0, 0, 1]
        assert bits_to_bytes(bits, msb_first=True) == b"H"

    def test_edge_invalid_bit_value(self) -> None:
        with pytest.raises(ValueError, match="0 ou 1"):
            bits_to_bytes([0, 2, 1, 0, 0, 0, 0, 0])

    def test_edge_fewer_than_8_bits(self) -> None:
        # Pas assez de bits pour un seul octet : resultat vide
        assert bits_to_bytes([1, 0, 1], msb_first=True) == b""


class TestDecodeAfskAscii:

    def test_interop_full_pipeline(self) -> None:
        # Verifie que la sortie de demodulate_afsk_bits est directement
        # consommable par bits_to_bytes puis decode ascii, bout en bout
        sr = 48000.0
        msg = "SatRX"
        sig = _make_afsk_signal(msg, BELL202, sr)
        result = decode_afsk_ascii(sig, sr, BELL202)
        assert result == msg

    def test_interop_errors_replace(self) -> None:
        # Un signal corrompu (bruit pur) produit des caracteres de remplacement,
        # pas une exception
        rng = np.random.default_rng(42)
        noise = rng.standard_normal(4800)
        result = decode_afsk_ascii(noise, 48000.0, BELL202, errors="replace")
        assert isinstance(result, str)
