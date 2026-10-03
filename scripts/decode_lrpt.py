#!/usr/bin/env python3
"""
Pipeline de decodage LRPT pour les enregistrements Meteor-M2.

Ordre du pipeline confirme (cf. tests/decode/test_pipeline_interop.py) :
  IQ brut (cs8) → correction frequence → Costas → decision QPSK → bits
  → recherche ASM (0x1ACFFC1D, non encode Viterbi) → Viterbi K=7 → derandomisation
  → RS(255,223) entrelace profondeur 4 → paquets CCSDS

Usage :
  poetry run python scripts/decode_lrpt.py data/raw/<fichier>.cs8
  poetry run python scripts/decode_lrpt.py data/raw/20260822T202850Z_METEOR-M2-3_137.700MHz.cs8
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

# Ajouter src/ au path si le script est lance directement
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constantes LRPT Meteor-M2 (confirmees cf. session 16/08/2026)
# ------------------------------------------------------------------ #
SYMBOL_RATE_BD = 72_000
SAMPLE_RATE_HZ = 2_048_000
SPS = SAMPLE_RATE_HZ / SYMBOL_RATE_BD  # ~28.44 samples/symbol
SPS_INT = int(round(SPS))              # 28

ASM_BYTES = bytes([0x1A, 0xCF, 0xFC, 0x1D])
ASM_BITS = 32
PAYLOAD_BYTES = 1020       # 4 x RS(255,223) interleaved
VITERBI_OUT_BITS = PAYLOAD_BYTES * 8   # 8160 bits decoded (avant rate-1/2)
VITERBI_IN_BITS = VITERBI_OUT_BITS * 2  # 16320 bits encoded

# Periode d'une frame dans le flux de bits bruts
FRAME_PERIOD_BITS = ASM_BITS + VITERBI_IN_BITS  # 32 + 16320 = 16352


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def load_chunk(
    path: Path,
    offset_bytes: int = 0,
    chunk_bytes: int = 50_000_000,
) -> NDArray[np.complex64]:
    """Charge un segment du fichier IQ cs8 (int8 paires I,Q)."""
    with path.open("rb") as f:
        f.seek(offset_bytes)
        raw = f.read(chunk_bytes)
    arr = np.frombuffer(raw, dtype=np.int8).astype(np.float32) / 127.5
    return (arr[0::2] + 1j * arr[1::2]).astype(np.complex64)


def freq_shift(
    iq: NDArray[np.complex64],
    shift_hz: float,
    fs: float = SAMPLE_RATE_HZ,
) -> NDArray[np.complex64]:
    """Decale le spectre de shift_hz Hz vers le haut."""
    t = np.arange(len(iq), dtype=np.float64) / fs
    return (iq * np.exp(1j * 2 * np.pi * shift_hz * t)).astype(np.complex64)


def symbols_to_bits_iq(symbols: NDArray[np.complex64]) -> list[int]:
    """Decision dure QPSK, convention I d'abord puis Q."""
    bits: list[int] = []
    for s in symbols:
        bits.append(0 if s.real >= 0.0 else 1)
        bits.append(0 if s.imag >= 0.0 else 1)
    return bits


def symbols_to_bits_qi(symbols: NDArray[np.complex64]) -> list[int]:
    """Decision dure QPSK, convention Q d'abord puis I."""
    bits: list[int] = []
    for s in symbols:
        bits.append(0 if s.imag >= 0.0 else 1)
        bits.append(0 if s.real >= 0.0 else 1)
    return bits


def bits_to_bytes_list(bits: list[int]) -> bytes:
    """Convertit une liste de bits (MSB first) en bytes."""
    n = len(bits) // 8
    return bytes(
        int("".join(str(b) for b in bits[i * 8:(i + 1) * 8]), 2)
        for i in range(n)
    )


def find_asm_positions(
    bits: list[int],
    max_hamming: int = 1,
) -> list[int]:
    from satrx.decode.frame_sync import find_sync_markers, DEFAULT_CCSDS_ASM
    matches = find_sync_markers(bits, marker=DEFAULT_CCSDS_ASM, max_hamming_distance=max_hamming)
    return [m.bit_offset for m in matches]


def decode_one_frame(
    frame_bits: list[int],
) -> tuple[bytes | None, int]:
    """
    Decodage d'un frame Viterbi-encode.
    Retourne (donnees_decodees, n_corrections_RS) ou (None, 0) si echec.
    """
    from satrx.decode.viterbi import viterbi_decode
    from satrx.decode.derandomize import derandomize
    from satrx.decode.reed_solomon import rs_decode_interleaved

    if len(frame_bits) < VITERBI_IN_BITS:
        return None, 0

    # Viterbi K=7, rendement 1/2
    decoded_bits = viterbi_decode(frame_bits[:VITERBI_IN_BITS])

    # Bits → octets
    payload = bits_to_bytes_list(decoded_bits)[:PAYLOAD_BYTES]
    if len(payload) < PAYLOAD_BYTES:
        return None, 0

    # Derandomisation CCSDS (XOR sequence PN, masque 0x95)
    derand = derandomize(payload)

    # RS decode + deentrelacement profondeur 4
    try:
        codewords_out = rs_decode_interleaved(list(derand), depth=4)
        # codewords_out : 4 listes de 223 octets (donnees, parity strippee par rs_decode)
        # Reassemblement en flux CCSDS : reentrelacement octet par octet
        data = bytes(
            codewords_out[i % 4][i // 4]
            for i in range(4 * 223)
        )
        return data, 0
    except Exception as exc:
        log.debug("RS echec frame : %s", exc)
        return None, 0


# ------------------------------------------------------------------ #
# Pipeline principal
# ------------------------------------------------------------------ #

def run_pipeline(
    iq_path: Path,
    offset_mb: int = 0,
    chunk_mb: int = 50,
    freq_offset_khz: float = 200.0,
    out_dir: Path = Path("data/processed"),
    max_frames: int = 200,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    t_global = time.perf_counter()

    # ---- 1. Chargement IQ ----
    log.info("✓ Chargement IQ : %s", iq_path.name)
    log.info("  Offset %d Mo, chunk %d Mo", offset_mb, chunk_mb)
    iq = load_chunk(iq_path, offset_mb * 1_000_000, chunk_mb * 1_000_000)
    duration_s = len(iq) / SAMPLE_RATE_HZ
    log.info("  %d echantillons, %.1f s de signal", len(iq), duration_s)

    # ---- 2. Decalage frequence grossier ----
    # Le signal est a +freq_offset_khz au-dessus de la frequence centrale HackRF.
    # Pour ramener le signal vers 0 Hz, on decale le spectre VERS LE BAS (signe negatif).
    log.info("⚙ Correction frequence -%.1f kHz (signal -> bande de base)", freq_offset_khz)
    iq_c = freq_shift(iq, -freq_offset_khz * 1000.0)

    # ---- 3. Affinage par estimation 4e puissance ----
    # Bloquer le DC (fuite LO HackRF) avant l'estimation pour eviter de confondre
    # le spike DC avec la porteuse QPSK.
    from satrx.demod.costas import estimate_frequency_offset_4th_power
    t1 = time.perf_counter()
    # Sous-ensemble central du chunk (evite transitoires debut/fin)
    n = len(iq_c)
    subset_start = n // 5
    subset_end = min(subset_start + 500_000, 4 * n // 5)
    subset = iq_c[subset_start:subset_end]
    subset_dcblocked = subset - subset.mean()
    coarse = estimate_frequency_offset_4th_power(subset_dcblocked, SAMPLE_RATE_HZ)
    log.info("  Offset residuel 4e puissance : %.1f Hz (%.2f s)", coarse, time.perf_counter() - t1)
    # Seuil : la correction 4e puissance est fiable uniquement si le signal est deja proche
    # de DC (i.e. coarse_shift grossier deja applique). Un residuel > 10 kHz apres le
    # decalage grossier indique que l'estimateur a accroche un interfèrent CW plutot que
    # la porteuse QPSK - on ignore alors la correction.
    if 300.0 < abs(coarse) <= 10_000.0:
        iq_c = freq_shift(iq_c, -coarse)
        log.info("  Correction residuelle appliquee : %.1f Hz", -coarse)
    elif abs(coarse) > 10_000.0:
        log.info("  Correction residuelle ignoree (%.1f Hz > 10 kHz - probable faux pic CW)", coarse)

    # ---- 4. Costas loop ----
    log.info("⚙ Costas loop QPSK...")
    from satrx.demod.costas import costas_loop_qpsk
    t2 = time.perf_counter()
    costas_res = costas_loop_qpsk(iq_c)
    symbols_all = costas_res.corrected_symbols
    log.info("  %d symboles en %.1f s", len(symbols_all), time.perf_counter() - t2)

    # ---- 5. Timing recovery ----
    log.info("⚙ Recouvrement timing symbole...")
    from satrx.demod.timing_recovery import estimate_symbol_timing_offset
    t3 = time.perf_counter()
    offset_frac = estimate_symbol_timing_offset(symbols_all, SPS_INT)
    offset_int = int(round(offset_frac))
    symbols = symbols_all[offset_int::SPS_INT]
    log.info("  Offset %.2f -> %d, %d symboles extraits en %.2f s",
             offset_frac, offset_int, len(symbols), time.perf_counter() - t3)

    # ---- 6. Decision QPSK → bits ----
    log.info("⚙ Decision QPSK hard (I,Q)...")
    bits_iq = symbols_to_bits_iq(symbols)
    log.info("  %d bits", len(bits_iq))

    # ---- 7. Recherche ASM ----
    log.info("⚙ Recherche ASM 0x1ACFFC1D...")
    t4 = time.perf_counter()
    positions = find_asm_positions(bits_iq, max_hamming=1)
    log.info("  %d positions trouvees en %.1f s", len(positions), time.perf_counter() - t4)

    # Si rien en I,Q → tenter Q,I (ambiguite de phase QPSK)
    bits_active = bits_iq
    if not positions:
        log.info("  Convention I,Q sans resultat - tentative Q,I...")
        bits_qi = symbols_to_bits_qi(symbols)
        positions = find_asm_positions(bits_qi, max_hamming=1)
        if positions:
            log.info("  ✓ ASM trouve avec convention Q,I : %d positions", len(positions))
            bits_active = bits_qi
        else:
            log.warning("⚠ Aucun ASM avec ni I,Q ni Q,I")
            # Tenter avec inversion des bits I et Q (autres ambiguites de phase)
            for flip_i, flip_q in [(True, False), (False, True), (True, True)]:
                sym_test = symbols.copy()
                if flip_i:
                    sym_test = sym_test.real * (-1) + 1j * sym_test.imag
                if flip_q:
                    sym_test = sym_test.real + 1j * sym_test.imag * (-1)
                bits_test = symbols_to_bits_iq(sym_test.astype(np.complex64))
                pos_test = find_asm_positions(bits_test, max_hamming=1)
                if pos_test:
                    log.info("  ✓ ASM trouve avec flip_i=%s flip_q=%s : %d positions",
                             flip_i, flip_q, len(pos_test))
                    positions = pos_test
                    bits_active = bits_test
                    break

    if not positions:
        log.error("✖ Aucun ASM trouve - signal absent, offset frequence incorrect, "
                  "ou offset de chunk defavorable")
        log.info("  Suggestion : essayer --offset-mb 60 --chunk-mb 50 pour un autre "
                 "segment du fichier")
        return

    # Periodicite
    if len(positions) >= 3:
        diffs = [positions[i+1] - positions[i] for i in range(min(6, len(positions)-1))]
        log.info("  Ecarts ASM consecutifs : %s", diffs)
        log.info("  Attendu ~%d bits (=%.1f s par frame)", FRAME_PERIOD_BITS,
                 FRAME_PERIOD_BITS / (SYMBOL_RATE_BD * 2))

    # ---- 8. Decodage des frames ----
    log.info("⚙ Decodage frames LRPT (max %d)...", max_frames)
    frames_ok = 0
    frames_err = 0
    total_rs_corr = 0
    decoded_chunks: list[bytes] = []

    for idx, pos in enumerate(positions[:max_frames]):
        frame_start = pos + ASM_BITS
        frame_end = frame_start + VITERBI_IN_BITS
        if frame_end > len(bits_active):
            break

        frame_bits = bits_active[frame_start:frame_end]
        data, n_corr = decode_one_frame(frame_bits)

        if data is not None:
            frames_ok += 1
            total_rs_corr += n_corr
            decoded_chunks.append(data)
        else:
            frames_err += 1

        if (idx + 1) % 20 == 0:
            log.info("  %d/%d frames : %d OK, %d erreurs, %d corrections RS",
                     idx + 1, min(len(positions), max_frames),
                     frames_ok, frames_err, total_rs_corr)

    log.info("✓ Decodage : %d OK / %d total, %d corrections RS total",
             frames_ok, frames_ok + frames_err, total_rs_corr)

    if not decoded_chunks:
        log.warning("⚠ Aucune frame decodee - signal trop faible ou pipeline desynchronise")
        return

    # ---- 9. Sauvegarde donnees brutes ----
    stem = iq_path.stem
    raw_out = out_dir / f"{stem}_decoded.bin"
    combined = b"".join(decoded_chunks)
    raw_out.write_bytes(combined)
    log.info("✓ Donnees decodees : %s (%d octets, %d frames)",
             raw_out, len(combined), frames_ok)

    # ---- 10. Extraction paquets CCSDS ----
    log.info("⚙ Extraction paquets CCSDS...")
    try:
        from satrx.decode.ccsds import parse_all_packets, demux_by_apid
        packets = parse_all_packets(combined)
        by_apid = demux_by_apid(packets)
        log.info("  %d paquets, %d APIDs distincts : %s",
                 len(packets), len(by_apid), sorted(by_apid.keys()))
        for apid in sorted(by_apid.keys()):
            pkts = by_apid[apid]
            data_bytes = sum(len(p.data) for p in pkts)
            log.info("  APID %3d : %4d paquets, %7d octets donnees", apid, len(pkts), data_bytes)
    except Exception as exc:
        log.warning("  Erreur parsing CCSDS : %s", exc)

    # ---- 11. Reconstruction image (si APIDs image presents) ----
    # APIDs Meteor-M2 3 : 64 (canal 1 visible), 65 (canal 2), 67 (canal 4 NIR)
    IMAGE_APIDS = {64: "ch1_visible", 65: "ch2_visible", 67: "ch4_nir"}
    try:
        from satrx.decode.ccsds import parse_all_packets, demux_by_apid
        from satrx.decode.jpeg_entropy import (
            BitReader,
            standard_ac_luminance_decode_table,
            standard_dc_luminance_decode_table,
        )
        from satrx.image.dct import STANDARD_LUMINANCE_QUANT_TABLE, scale_quantization_table
        from satrx.image.io import save_image
        from satrx.image.mcu import decode_mcu_image

        packets = parse_all_packets(combined)
        by_apid = demux_by_apid(packets)
        found_image = False

        for apid, label in IMAGE_APIDS.items():
            if apid not in by_apid:
                continue
            log.info("⚙ Reconstruction image APID %d (%s)...", apid, label)
            apid_data = b"".join(bytes(p.data) for p in by_apid[apid])
            if len(apid_data) < 128:
                log.info("  Trop peu de donnees APID %d (%d octets)", apid, len(apid_data))
                continue

            dc_table = standard_dc_luminance_decode_table()
            ac_table = standard_ac_luminance_decode_table()
            quant_table = scale_quantization_table(50, STANDARD_LUMINANCE_QUANT_TABLE)

            # Tenter de deviner les dimensions depuis la quantite de donnees
            n_bytes = len(apid_data)
            # Meteor-M2 3 : 1568 pixels de large, 8 lignes par MCU strip
            width = 1568
            # Combien de strips de 8 lignes peut-on decoder ?
            pixels_per_strip = width * 8
            bytes_per_strip_est = max(1, pixels_per_strip // 2)  # JPEG ~50% compression estimee
            n_strips = max(1, n_bytes // bytes_per_strip_est)
            height = max(8, min(n_strips * 8, 4096))
            # Arrondir la hauteur au multiple de 8 le plus proche
            height = (height // 8) * 8

            log.info("  Donnees : %d octets, dimensions estimees %dx%d", n_bytes, width, height)

            try:
                reader = BitReader(apid_data)
                image = decode_mcu_image(
                    reader,
                    dc_table=dc_table,
                    ac_table=ac_table,
                    quant_table=quant_table,
                    width_px=width,
                    height_px=height,
                )
                img_path = out_dir / f"{stem}_{label}.png"
                save_image(image, img_path)
                log.info("  ✓ Image sauvegardee : %s (%dx%d)",
                         img_path, image.shape[1], image.shape[0])
                found_image = True
            except Exception as exc:
                log.warning("  Reconstruction image APID %d echouee : %s", apid, exc)

        if not found_image:
            log.info("  Aucune image reconstruite (donnees insuffisantes ou format inattendu)")
    except Exception as exc:
        log.warning("  Etape reconstruction image ignoree : %s", exc)

    log.info("⚙ Duree totale pipeline : %.1f s", time.perf_counter() - t_global)


# ------------------------------------------------------------------ #
# CLI
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decodage LRPT Meteor-M2 depuis un fichier IQ cs8",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("iq_file", type=Path, help="Fichier IQ .cs8")
    parser.add_argument(
        "--offset-mb", type=int, default=0,
        help="Offset de lecture dans le fichier (Mo)",
    )
    parser.add_argument(
        "--chunk-mb", type=int, default=50,
        help="Taille du segment a traiter (Mo). 50 Mo ~ 12 s de signal.",
    )
    parser.add_argument(
        "--freq-offset-khz", type=float, default=200.0,
        help="Decalage frequence en kHz entre le centre HackRF et le signal LRPT "
             "(137.9 MHz - 137.7 MHz = +200 kHz)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("data/processed"),
        help="Repertoire de sortie",
    )
    parser.add_argument(
        "--max-frames", type=int, default=200,
        help="Nombre maximum de frames a decoder",
    )
    args = parser.parse_args()

    if not args.iq_file.exists():
        log.error("✖ Fichier introuvable : %s", args.iq_file)
        sys.exit(1)

    run_pipeline(
        iq_path=args.iq_file,
        offset_mb=args.offset_mb,
        chunk_mb=args.chunk_mb,
        freq_offset_khz=args.freq_offset_khz,
        out_dir=args.out_dir,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
