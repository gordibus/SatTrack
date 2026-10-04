from __future__ import annotations

import pytest

from satrx.acquisition.satellite_catalog import (
    CATALOG,
    hackrf_center_with_ppm,
    lookup_by_name,
    lookup_by_norad,
)


class TestLookupByName:

    def test_meteor_m2_3_exact(self) -> None:
        p = lookup_by_name("METEOR-M2 3")
        assert p is not None
        assert p.norad_id == 57166
        assert p.tx_freq_hz == 137_900_000.0

    def test_case_insensitive(self) -> None:
        p = lookup_by_name("meteor-m2 3")
        assert p is not None
        assert p.norad_id == 57166

    def test_partial_match_meteor(self) -> None:
        p = lookup_by_name("METEOR-M2 4")
        assert p is not None
        assert p.norad_id == 59051

    def test_noaa_18(self) -> None:
        p = lookup_by_name("NOAA 18")
        assert p is not None
        assert p.tx_freq_hz == 137_912_500.0

    def test_unknown_returns_none(self) -> None:
        assert lookup_by_name("SATELLITE_INCONNU_XYZ") is None


class TestLookupByNorad:

    def test_meteor_m2_3(self) -> None:
        p = lookup_by_norad(57166)
        assert p is not None
        assert p.name == "METEOR-M2 3"

    def test_noaa_19(self) -> None:
        p = lookup_by_norad(33591)
        assert p is not None
        assert p.tx_freq_hz == 137_100_000.0

    def test_unknown_norad_returns_none(self) -> None:
        assert lookup_by_norad(99999) is None


class TestHackrfCenterWithPpm:

    def test_no_ppm_correction(self) -> None:
        p = lookup_by_name("METEOR-M2 3")
        assert p is not None
        result = hackrf_center_with_ppm(p, 0)
        assert result == p.hackrf_center_hz
        assert result == 137_700_000.0

    def test_ppm_300_shifts_frequency_down(self) -> None:
        # PPM +300 = oscillateur trop haut, on commande plus bas
        # 137_700_000 / (1 + 300/1e6) = 137_658_702 Hz environ
        p = lookup_by_name("METEOR-M2 3")
        assert p is not None
        result = hackrf_center_with_ppm(p, 300)
        assert result < p.hackrf_center_hz
        assert abs(result - 137_658_702.0) < 10.0

    def test_ppm_correction_applied_correctly(self) -> None:
        # Verifier que l'OL reel apres correction est bien a hackrf_center_hz
        # actual_lo = commanded * (1 + ppm/1e6)
        p = lookup_by_name("METEOR-M2 3")
        assert p is not None
        ppm = 300
        commanded = hackrf_center_with_ppm(p, ppm)
        actual_lo = commanded * (1.0 + ppm / 1_000_000.0)
        assert abs(actual_lo - p.hackrf_center_hz) < 1.0  # erreur < 1 Hz


class TestCatalogIntegrity:

    def test_all_profiles_have_positive_freq(self) -> None:
        for p in CATALOG:
            assert p.tx_freq_hz > 0, f"{p.name}: tx_freq_hz invalide"
            assert p.hackrf_center_hz > 0, f"{p.name}: hackrf_center_hz invalide"

    def test_all_profiles_have_nonzero_offset(self) -> None:
        # Tous les satellites doivent avoir un offset DC non nul (eviter le spike LO)
        for p in CATALOG:
            assert p.lo_offset_hz != 0.0, f"{p.name}: lo_offset_hz = 0 (pas d'offset DC)"

    def test_freq_offset_khz_positive_for_all(self) -> None:
        # freq_offset_khz doit etre positif (signal au-dessus du centre HackRF)
        for p in CATALOG:
            assert p.freq_offset_khz > 0, f"{p.name}: freq_offset_khz negatif"

    def test_interop_with_recording_params(self) -> None:
        """Le signal satellite doit apparaitre a freq_offset_khz du centre apres correction PPM.

        Convention :
          center_freq_hz = frequence desiree de l'OL (ex. 137.7 MHz)
          center_freq_hz_ppm_corrected = frequence commandee au HackRF (ex. 137.659 MHz)
          L'OL reel = commanded * (1 + ppm/1e6) = center_freq_hz (desired)
          signal_offset = tx_freq - center_freq_hz = freq_offset_khz kHz
        """
        from satrx.acquisition.params import RecordingParams

        p = lookup_by_name("METEOR-M2 3")
        assert p is not None
        # center_freq_hz = frequence DESIREE de l'OL (pas la frequence commandee apres PPM)
        params = RecordingParams(
            satellite_name=p.name,
            center_freq_hz=p.hackrf_center_hz,   # 137_700_000
            sample_rate_hz=2_048_000.0,
            duration_s=600.0,
            gain_db=30.0,
            lna_gain_db=32.0,
            ppm_correction=300,
            satellite_freq_hz=p.tx_freq_hz,
            freq_offset_khz=p.freq_offset_khz,
        )
        # L'OL reel apres correction PPM doit etre = center_freq_hz desiree (137.7 MHz)
        actual_lo = params.center_freq_hz_ppm_corrected * (1.0 + params.ppm_correction / 1_000_000.0)
        assert abs(actual_lo - p.hackrf_center_hz) < 1.0  # < 1 Hz d'erreur

        # Le signal satellite doit apparaitre exactement a freq_offset_khz du centre desire
        signal_offset_hz = p.tx_freq_hz - p.hackrf_center_hz
        assert abs(signal_offset_hz - p.freq_offset_khz * 1000.0) < 0.01
