"""Module de simulation GMR-1 - lab audit operateur (B8).

Usage uniquement dans un environnement lab isole avec autorisation ecrite
de l'operateur/FAI (cf. cahier des charges § audit lab operateur).
"""
from satrx.security.gmr1.a5gmr1 import (
    decrypt_burst_data,
    encrypt_burst_data,
    generate_keystream,
    initialize,
)
from satrx.security.gmr1.burst import (
    decode_burst_data,
    encode_normal_burst,
    generate_idle_burst,
)
from satrx.security.gmr1.gmsk import gaussian_freq_pulse, gmsk_modulate, to_cs8
from satrx.security.gmr1.fraud import (
    FraudAlert,
    SessionRecord,
    analyze_session_log,
    detect_billing_gaps,
    detect_sequence_replay,
    detect_simultaneous_sessions,
    inject_billing_gap,
    inject_clone_attack,
    inject_replay_attack,
    simulate_normal_sessions,
)
from satrx.security.gmr1.cryptanalysis import (
    CryptanalysisResult,
    attack_known_plaintext,
    brute_force_r1,
    recover_keystream,
    verify_state,
)
from satrx.security.gmr1.demod import (
    DemodResult,
    demodulate_signal,
    extract_data_from_burst,
    find_best_timing_offset,
    gmsk_demodulate_soft,
    locate_midambles,
)
from satrx.security.gmr1.signal_gen import (
    Gmr1SignalSpec,
    generate_gmr1_signal,
    save_gmr1_iq,
)

__all__ = [
    "SessionRecord",
    "FraudAlert",
    "simulate_normal_sessions",
    "inject_clone_attack",
    "inject_replay_attack",
    "inject_billing_gap",
    "detect_simultaneous_sessions",
    "detect_sequence_replay",
    "detect_billing_gaps",
    "analyze_session_log",
    "CryptanalysisResult",
    "recover_keystream",
    "brute_force_r1",
    "verify_state",
    "attack_known_plaintext",
    "DemodResult",
    "gmsk_demodulate_soft",
    "find_best_timing_offset",
    "locate_midambles",
    "extract_data_from_burst",
    "demodulate_signal",
    "encode_normal_burst",
    "decode_burst_data",
    "generate_idle_burst",
    "gaussian_freq_pulse",
    "gmsk_modulate",
    "to_cs8",
    "initialize",
    "generate_keystream",
    "encrypt_burst_data",
    "decrypt_burst_data",
    "Gmr1SignalSpec",
    "generate_gmr1_signal",
    "save_gmr1_iq",
]
