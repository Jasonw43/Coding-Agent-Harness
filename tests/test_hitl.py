"""Deterministic tests for the HITL approval state machine."""

from pathlib import Path

from cah.hitl.state_machine import HITLStateMachine


def test_full_transitions(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=300)
    rec, token = sm.submit(action_id="a1", reason="danger")
    assert rec.state == "PENDING" and token
    assert sm.approve("a1", token, "user").state == "APPROVED"
    # idempotent: approving again stays APPROVED
    assert sm.approve("a1", token, "user").state == "APPROVED"


def test_reject_and_expiry(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=-1)
    rec, token = sm.submit(action_id="a2", reason="danger")
    assert sm.reject("a2", token, "user").state == "REJECTED"
    rec2, _ = sm.submit(action_id="a3", reason="x")
    expired = sm.resolve_expired()
    assert any(r.action_id == "a3" and r.state == "EXPIRED" for r in expired)


def test_wrong_token_rejected(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=300)
    sm.submit(action_id="a4", reason="x")
    try:
        sm.approve("a4", "wrong", "user")
        assert False, "should raise PermissionError"
    except PermissionError:
        pass


def test_persistence_across_instances(tmp_path):
    store = tmp_path / "approvals.json"
    sm1 = HITLStateMachine(store_path=store, timeout_s=300)
    rec, token = sm1.submit(action_id="a5", reason="persist")
    sm2 = HITLStateMachine(store_path=store, timeout_s=300)
    rec2 = sm2.get("a5")
    assert rec2 is not None and rec2.action_id == "a5"
    assert sm2.approve("a5", token, "user").state == "APPROVED"
