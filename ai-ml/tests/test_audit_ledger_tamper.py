"""
Unit tests for SubSense DGMS Cryptographic Audit Ledger & Tamper Detection.
Proves:
1. Multi-party sign-off enforcement for threshold revisions > 15%.
2. Tamper test: Mutates historical stored data on disk and asserts detection by the cryptographic verifier.
"""

import json
import os
import pytest

from governance.audit_ledger import (
    CryptographicAuditLedger,
    LedgerTamperDetectedException,
    MissingSignOffException,
)


class TestAuditLedgerAndTamperDetection:
    def test_small_revision_succeeds_single_signatory(self, tmp_path):
        ledger_path = str(tmp_path / "test_ledger.json")
        ledger = CryptographicAuditLedger(ledger_file_path=ledger_path, multi_party_threshold_pct=15.0)

        # 10% revision (0.20 -> 0.22)
        entry = ledger.record_revision(
            threshold_name="theta_vel_mm_h",
            old_value=0.20,
            new_value=0.22,
            justification="Minor seasonal tuning",
            author_id="GEO_ENG_01",
            signatories=["GEO_ENG_01"],
        )
        assert entry.entry_id == "REV-00001"
        assert ledger.verify_chain_integrity() is True

    def test_large_revision_without_multi_party_is_blocked(self, tmp_path):
        ledger_path = str(tmp_path / "test_ledger.json")
        ledger = CryptographicAuditLedger(ledger_file_path=ledger_path, multi_party_threshold_pct=15.0)

        # 50% revision (0.20 -> 0.30) requires >= 2 distinct signatories
        with pytest.raises(MissingSignOffException) as exc_info:
            ledger.record_revision(
                threshold_name="theta_vel_mm_h",
                old_value=0.20,
                new_value=0.30,
                justification="Major loosening of velocity threshold",
                author_id="GEO_ENG_01",
                signatories=["GEO_ENG_01"],  # Only 1 signatory!
            )
        assert "Requires >= 2 distinct authorized signatories" in str(exc_info.value)

    def test_large_revision_with_multi_party_succeeds(self, tmp_path):
        ledger_path = str(tmp_path / "test_ledger.json")
        ledger = CryptographicAuditLedger(ledger_file_path=ledger_path, multi_party_threshold_pct=15.0)

        # 50% revision with 2 distinct authorized signatories
        entry = ledger.record_revision(
            threshold_name="theta_vel_mm_h",
            old_value=0.20,
            new_value=0.30,
            justification="DGMS approved seasonal adjustment",
            author_id="GEO_ENG_01",
            signatories=["GEO_ENG_01", "DGMS_INSPECTOR_04"],
        )
        assert entry.entry_id == "REV-00001"
        assert ledger.verify_chain_integrity() is True

    def test_disk_file_mutation_triggers_tamper_detection(self, tmp_path):
        """
        Safety-critical verification: Actually mutates historical stored data on disk
        and asserts that verify_chain_integrity() catches it.
        """
        ledger_path = str(tmp_path / "tamper_target_ledger.json")
        ledger = CryptographicAuditLedger(ledger_file_path=ledger_path, multi_party_threshold_pct=15.0)

        # Record two legitimate revisions
        ledger.record_revision(
            threshold_name="theta_vel_mm_h",
            old_value=0.20,
            new_value=0.22,
            justification="First revision",
            author_id="GEO_ENG_01",
            signatories=["GEO_ENG_01"],
        )
        ledger.record_revision(
            threshold_name="theta_accel_mm_h2",
            old_value=0.050,
            new_value=0.052,
            justification="Second revision",
            author_id="GEO_ENG_01",
            signatories=["GEO_ENG_01"],
        )

        # Verify initial clean state
        assert ledger.verify_chain_integrity() is True

        # TAMPER: Directly read JSON from disk, alter the first revision's new_value from 0.22 to 0.99
        with open(ledger_path, "r", encoding="utf-8") as f:
            disk_entries = json.load(f)

        assert len(disk_entries) == 3  # Genesis + 2 revisions
        disk_entries[1]["new_value"] = 0.99  # Corrupt historical payload!

        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(disk_entries, f, indent=2)

        # Run integrity verification - MUST detect disk corruption!
        with pytest.raises(LedgerTamperDetectedException) as exc_info:
            ledger.verify_chain_integrity()

        assert "TAMPER DETECTED" in str(exc_info.value)
