"""HITL (human-in-the-loop) approval state machine with JSON persistence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


@dataclass
class ApprovalRecord:
    """One approval request and its lifecycle."""

    action_id: str
    state: str = ApprovalState.PENDING.value
    token_hash: str = ""
    reason: str = ""
    decided_by: str = ""
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class HITLStateMachine:
    """Persist approval requests and enforce the approval state transitions.

    States: PENDING -> APPROVED | REJECTED | EXPIRED | CANCELED.
    Approve/reject require the one-time token returned by ``submit``.
    Re-deciding an already-decided action is idempotent.
    """

    def __init__(self, store_path: Path, timeout_s: int = 300) -> None:
        self.store_path = Path(store_path)
        self.timeout_s = timeout_s
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._records = data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            # corrupt store: back it up and start fresh (fail-safe)
            backup = self.store_path.with_suffix(".json.bak")
            try:
                os.replace(self.store_path, backup)
            except OSError:
                pass
            self._records = {}

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.store_path.parent), prefix=".approvals-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.store_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    # ---- query ----

    def get(self, action_id: str) -> ApprovalRecord | None:
        raw = self._records.get(action_id)
        return ApprovalRecord(**raw) if raw else None

    def list_pending(self) -> list[ApprovalRecord]:
        return [
            ApprovalRecord(**raw)
            for raw in self._records.values()
            if raw.get("state") == ApprovalState.PENDING.value
        ]

    # ---- transitions ----

    def submit(self, action_id: str, reason: str) -> tuple[ApprovalRecord, str]:
        if action_id in self._records:
            raise ValueError(f"approval already exists for action {action_id!r}")
        token = secrets.token_urlsafe(16)
        record = ApprovalRecord(
            action_id=action_id,
            state=ApprovalState.PENDING.value,
            token_hash=_hash_token(token),
            reason=reason,
        )
        self._records[action_id] = asdict(record)
        self._save()
        return record, token

    def _decide(
        self, action_id: str, token: str, decided_by: str, new_state: ApprovalState
    ) -> ApprovalRecord:
        raw = self._records.get(action_id)
        if raw is None:
            raise KeyError(f"no approval for action {action_id!r}")
        if not secrets.compare_digest(raw["token_hash"], _hash_token(token)):
            raise PermissionError("invalid approval token")
        if raw["state"] != ApprovalState.PENDING.value:
            # idempotent: return the already-decided record unchanged
            return ApprovalRecord(**raw)
        raw["state"] = new_state.value
        raw["decided_by"] = decided_by
        raw["decided_at"] = time.time()
        self._records[action_id] = raw
        self._save()
        return ApprovalRecord(**raw)

    def approve(self, action_id: str, token: str, decided_by: str) -> ApprovalRecord:
        return self._decide(action_id, token, decided_by, ApprovalState.APPROVED)

    def reject(self, action_id: str, token: str, decided_by: str) -> ApprovalRecord:
        return self._decide(action_id, token, decided_by, ApprovalState.REJECTED)

    def cancel(self, action_id: str, decided_by: str) -> ApprovalRecord:
        raw = self._records.get(action_id)
        if raw is None:
            raise KeyError(f"no approval for action {action_id!r}")
        if raw["state"] != ApprovalState.PENDING.value:
            return ApprovalRecord(**raw)
        raw["state"] = ApprovalState.CANCELED.value
        raw["decided_by"] = decided_by
        raw["decided_at"] = time.time()
        self._records[action_id] = raw
        self._save()
        return ApprovalRecord(**raw)

    def resolve_expired(self) -> list[ApprovalRecord]:
        """Mark stale PENDING records as EXPIRED (fail-safe default)."""
        now = time.time()
        expired: list[ApprovalRecord] = []
        for action_id, raw in self._records.items():
            if raw.get("state") != ApprovalState.PENDING.value:
                continue
            age = now - raw.get("created_at", now)
            if self.timeout_s <= 0 or age >= self.timeout_s:
                raw["state"] = ApprovalState.EXPIRED.value
                raw["decided_by"] = "system"
                raw["decided_at"] = now
                self._records[action_id] = raw
                expired.append(ApprovalRecord(**raw))
        if expired:
            self._save()
        return expired
