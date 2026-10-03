import numpy as np
import pytest

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

N_SUB = 4
N_FRAMES = 20
RNG = np.random.default_rng(0)


def _base_records() -> list[SessionRecord]:
    return simulate_normal_sessions(N_SUB, N_FRAMES, rng=np.random.default_rng(0))


class TestSimulateNormalSessions:

    def test_nombre_enregistrements(self) -> None:
        records = _base_records()
        assert len(records) == N_SUB * N_FRAMES

    def test_sequence_strictement_croissante(self) -> None:
        records = _base_records()
        by_sub: dict[int, list[int]] = {}
        for r in records:
            by_sub.setdefault(r.imsi_hash, []).append(r.seq_num)
        for imsi, seqs in by_sub.items():
            for i in range(1, len(seqs)):
                assert seqs[i] > seqs[i - 1], f"sequence non monotone pour IMSI {imsi}"

    def test_tous_factures(self) -> None:
        records = _base_records()
        assert all(r.billed for r in records)

    def test_n_subscribers_invalide(self) -> None:
        with pytest.raises(ValueError, match="n_subscribers"):
            simulate_normal_sessions(n_subscribers=0, n_frames=10)

    def test_n_frames_invalide(self) -> None:
        with pytest.raises(ValueError, match="n_frames"):
            simulate_normal_sessions(n_subscribers=2, n_frames=0)


class TestDetectSimultaneousSessions:

    def test_aucune_alerte_sur_sessions_normales(self) -> None:
        records = _base_records()
        alerts = detect_simultaneous_sessions(records)
        clone_alerts = [a for a in alerts if a.alert_type == "clone"]
        assert len(clone_alerts) == 0

    def test_clone_detecte(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        clone_slot = N_SUB  # slot hors des slots normaux
        injected = inject_clone_attack(records, target, start_frame=5, clone_slot=clone_slot)
        alerts = detect_simultaneous_sessions(injected)
        assert any(a.alert_type == "clone" and a.imsi_hash == target for a in alerts)

    def test_alerte_severite_high(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_clone_attack(records, target, start_frame=3, clone_slot=7)
        alerts = detect_simultaneous_sessions(injected)
        clone = next(a for a in alerts if a.alert_type == "clone")
        assert clone.severity == "HIGH"

    def test_frame_refs_non_vide(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_clone_attack(records, target, start_frame=2, clone_slot=7)
        alerts = detect_simultaneous_sessions(injected)
        clone = next(a for a in alerts if a.alert_type == "clone")
        assert len(clone.frame_refs) > 0


class TestDetectSequenceReplay:

    def test_aucune_alerte_sur_sessions_normales(self) -> None:
        records = _base_records()
        alerts = detect_sequence_replay(records)
        assert len(alerts) == 0

    def test_replay_detecte(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_replay_attack(records, target, replay_at_frame=10)
        alerts = detect_sequence_replay(injected)
        assert any(a.alert_type == "replay" and a.imsi_hash == target for a in alerts)

    def test_details_contient_regression(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_replay_attack(records, target, replay_at_frame=8)
        alerts = detect_sequence_replay(injected)
        replay = next(a for a in alerts if a.alert_type == "replay")
        assert "regression" in replay.details.lower() or "replay" in replay.details.lower()


class TestDetectBillingGaps:

    def test_aucune_alerte_sur_sessions_normales(self) -> None:
        records = _base_records()
        alerts = detect_billing_gaps(records, max_unbilled_frames=3)
        assert len(alerts) == 0

    def test_gap_detecte(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_billing_gap(records, target, gap_start_frame=5, gap_size=8)
        alerts = detect_billing_gaps(injected, max_unbilled_frames=3)
        assert any(a.alert_type == "billing_gap" and a.imsi_hash == target for a in alerts)

    def test_gap_sous_seuil_pas_alerté(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_billing_gap(records, target, gap_start_frame=5, gap_size=2)
        alerts = detect_billing_gaps(injected, max_unbilled_frames=5)
        assert not any(a.alert_type == "billing_gap" and a.imsi_hash == target for a in alerts)

    def test_severite_medium(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_billing_gap(records, target, gap_start_frame=3, gap_size=6)
        alerts = detect_billing_gaps(injected, max_unbilled_frames=3)
        gap_alert = next(a for a in alerts if a.alert_type == "billing_gap")
        assert gap_alert.severity == "MEDIUM"


class TestAnalyzeSessionLog:

    def test_retourne_liste(self) -> None:
        records = _base_records()
        alerts = analyze_session_log(records)
        assert isinstance(alerts, list)

    def test_high_avant_medium(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        injected = inject_clone_attack(records, target, start_frame=2, clone_slot=7)
        injected = inject_billing_gap(injected, target, gap_start_frame=10, gap_size=6)
        alerts = analyze_session_log(injected)
        severities = [a.severity for a in alerts]
        high_idx = [i for i, s in enumerate(severities) if s == "HIGH"]
        medium_idx = [i for i, s in enumerate(severities) if s == "MEDIUM"]
        if high_idx and medium_idx:
            assert max(high_idx) < min(medium_idx), "HIGH doit preceder MEDIUM"

    def test_pipeline_detecte_les_trois_types(self) -> None:
        records = _base_records()
        target = records[0].imsi_hash
        # Injecter les trois types de fraude
        injected = inject_clone_attack(records, target, start_frame=2, clone_slot=7)
        injected = inject_replay_attack(injected, target, replay_at_frame=12)
        injected = inject_billing_gap(injected, target, gap_start_frame=5, gap_size=6)
        alerts = analyze_session_log(injected)
        types_detectes = {a.alert_type for a in alerts}
        assert "clone" in types_detectes
        assert "replay" in types_detectes
        assert "billing_gap" in types_detectes
