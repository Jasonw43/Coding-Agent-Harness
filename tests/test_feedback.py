"""Deterministic tests for feedback validators."""

from cah.feedback.validators import TestRunnerValidator


def test_validator_reports_failure(tmp_path):
    v = TestRunnerValidator(command=["python", "-c", "raise SystemExit(1)"])
    fb = v.validate(tmp_path)
    assert not fb.ok
    assert fb.summary


def test_validator_reports_success(tmp_path):
    v = TestRunnerValidator(command=["python", "-c", "pass"])
    fb = v.validate(tmp_path)
    assert fb.ok and fb.failures == []


def test_validator_parses_failure_lines(tmp_path):
    v = TestRunnerValidator(
        command=["python", "-c", "import sys; print('FAILED test_x'); sys.exit(2)"]
    )
    fb = v.validate(tmp_path)
    assert not fb.ok
    assert any("FAILED" in line for line in fb.failures)
    assert "exit code 2" in fb.summary
