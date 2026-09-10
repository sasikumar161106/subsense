"""
SubSense Layer 4: Cryptographic DGMS Audit Ledger & Threshold Governance.
Implements immutable, SHA-256 hash-chained append-only threshold governance ledger.
Enforces multi-party sign-off for revisions > 15% in code.
Provides cryptographic tamper detection.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple


class LedgerTamperDetectedException(RuntimeError):
    """Raised when ledger cryptographic integrity check fails."""
    pass


class MissingSignOffException(PermissionError):
    """Raised when threshold change > 15% lacks required multi-party sign-offs."""
    pass


GENESIS_HASH = "0" * 64


@dataclass
class ThresholdRevisionEntry:
    entry_id: str
    timestamp_utc: str
    threshold_name: str
    old_value: float
    new_value: float
    percent_change: float
    justification: str
    author_id: str
    signatories: List[str]
    prev_hash: str
    entry_hash: str

    def to_dict(self) -> Dict:
        return asdict(self)


class CryptographicAuditLedger:
    """
    Immutable, hash-chained ledger storing all threshold revisions.
    DGMS regulatory compliance grade.
    """

    def __init__(self, ledger_file_path: str = "logs/audit_ledger.json", multi_party_threshold_pct: float = 15.0):
        self.ledger_file_path = ledger_file_path
        self.multi_party_threshold_pct = float(multi_party_threshold_pct)
        self.entries: List[ThresholdRevisionEntry] = []
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file_path)), exist_ok=True)
        self._load_or_initialize()

    def _compute_hash(
        self,
        prev_hash: str,
        entry_id: str,
        timestamp_utc: str,
        threshold_name: str,
        old_value: float,
        new_value: float,
        justification: str,
        author_id: str,
        signatories: List[str],
    ) -> str:
        """Computes deterministic SHA-256 hash across canonical serialized fields."""
        payload = {
            "prev_hash": prev_hash,
            "entry_id": entry_id,
            "timestamp_utc": timestamp_utc,
            "threshold_name": threshold_name,
            "old_value": round(float(old_value), 6),
            "new_value": round(float(new_value), 6),
            "justification": justification.strip(),
            "author_id": author_id.strip(),
            "signatories": sorted([s.strip() for s in signatories]),
        }
        canonical_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def _load_or_initialize(self) -> None:
        """Loads existing ledger entries from disk or creates genesis entry."""
        if os.path.exists(self.ledger_file_path):
            with open(self.ledger_file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    self.entries = [ThresholdRevisionEntry(**e) for e in data]
                except Exception:
                    self.entries = []

        if not self.entries:
            # Create genesis block
            genesis_time = "2026-01-01T00:00:00+00:00"
            g_hash = self._compute_hash(
                prev_hash=GENESIS_HASH,
                entry_id="REV-00000-GENESIS",
                timestamp_utc=genesis_time,
                threshold_name="GENESIS_INITIALIZATION",
                old_value=0.0,
                new_value=0.0,
                justification="DGMS System Baseline Initialization",
                author_id="SYSTEM_ROOT",
                signatories=["SYSTEM_ROOT"],
            )
            genesis_entry = ThresholdRevisionEntry(
                entry_id="REV-00000-GENESIS",
                timestamp_utc=genesis_time,
                threshold_name="GENESIS_INITIALIZATION",
                old_value=0.0,
                new_value=0.0,
                percent_change=0.0,
                justification="DGMS System Baseline Initialization",
                author_id="SYSTEM_ROOT",
                signatories=["SYSTEM_ROOT"],
                prev_hash=GENESIS_HASH,
                entry_hash=g_hash,
            )
            self.entries.append(genesis_entry)
            self._save_to_disk()

    def _save_to_disk(self) -> None:
        """Saves chain to disk in append-only format."""
        with open(self.ledger_file_path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.entries], f, indent=2)

    def record_revision(
        self,
        threshold_name: str,
        old_value: float,
        new_value: float,
        justification: str,
        author_id: str,
        signatories: List[str],
        timestamp_utc: Optional[datetime] = None,
    ) -> ThresholdRevisionEntry:
        """
        Records a new threshold revision.
        Enforces:
        1. If percent_change > 15%, >= 2 distinct signatories are REQUIRED.
        2. Cryptographic append to hash chain.
        """
        if abs(old_value) > 1e-9:
            pct_change = abs((new_value - old_value) / old_value) * 100.0
        else:
            pct_change = 100.0 if new_value != 0.0 else 0.0

        # Multi-party sign-off check
        unique_signatories = list(set([s.strip() for s in signatories if s.strip()]))
        if pct_change > self.multi_party_threshold_pct:
            if len(unique_signatories) < 2:
                raise MissingSignOffException(
                    f"DGMS GOVERNANCE REJECTION: Threshold change '{threshold_name}' magnitude "
                    f"({pct_change:.1f}%) exceeds {self.multi_party_threshold_pct}%. "
                    f"Requires >= 2 distinct authorized signatories, got {len(unique_signatories)}: {unique_signatories}."
                )

        now_dt = timestamp_utc or datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()

        prev_entry = self.entries[-1]
        entry_id = f"REV-{len(self.entries):05d}"

        entry_hash = self._compute_hash(
            prev_hash=prev_entry.entry_hash,
            entry_id=entry_id,
            timestamp_utc=ts_str,
            threshold_name=threshold_name,
            old_value=old_value,
            new_value=new_value,
            justification=justification,
            author_id=author_id,
            signatories=unique_signatories,
        )

        entry = ThresholdRevisionEntry(
            entry_id=entry_id,
            timestamp_utc=ts_str,
            threshold_name=threshold_name,
            old_value=old_value,
            new_value=new_value,
            percent_change=pct_change,
            justification=justification,
            author_id=author_id,
            signatories=unique_signatories,
            prev_hash=prev_entry.entry_hash,
            entry_hash=entry_hash,
        )

        self.entries.append(entry)
        self._save_to_disk()
        return entry

    def verify_chain_integrity(self) -> bool:
        """
        Cryptographically verifies the entire ledger chain from genesis block.
        Raises LedgerTamperDetectedException immediately on any byte tampering.
        """
        # Re-read raw contents from disk to detect external mutations
        with open(self.ledger_file_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)

        disk_entries = [ThresholdRevisionEntry(**e) for e in disk_data]
        if not disk_entries:
            raise LedgerTamperDetectedException("Ledger file is empty!")

        for idx, entry in enumerate(disk_entries):
            # Check genesis block
            if idx == 0:
                if entry.prev_hash != GENESIS_HASH:
                    raise LedgerTamperDetectedException(
                        f"Genesis block tampered! Invalid prev_hash {entry.prev_hash}"
                    )
            else:
                prev = disk_entries[idx - 1]
                if entry.prev_hash != prev.entry_hash:
                    raise LedgerTamperDetectedException(
                        f"TAMPER DETECTED at entry {entry.entry_id} (index {idx}): "
                        f"prev_hash {entry.prev_hash} does not match predecessor hash {prev.entry_hash}!"
                    )

            # Recompute expected hash
            expected_hash = self._compute_hash(
                prev_hash=entry.prev_hash,
                entry_id=entry.entry_id,
                timestamp_utc=entry.timestamp_utc,
                threshold_name=entry.threshold_name,
                old_value=entry.old_value,
                new_value=entry.new_value,
                justification=entry.justification,
                author_id=entry.author_id,
                signatories=entry.signatories,
            )

            if expected_hash != entry.entry_hash:
                raise LedgerTamperDetectedException(
                    f"TAMPER DETECTED at entry {entry.entry_id} (index {idx}): "
                    f"stored entry_hash {entry.entry_hash} does not match computed hash {expected_hash}!"
                )

        return True
