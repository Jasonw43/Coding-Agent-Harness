"""Deterministic tests for the Gradio demo console helpers."""

import time

from cah.web.hf_console import DemoConsole


def test_demo_approval_flow(tmp_path):
    console = DemoConsole(store_dir=tmp_path)
    run_id = console.start_demo()
    assert run_id

    pending = []
    for _ in range(30):
        pending = console.pending()
        if pending:
            break
        time.sleep(0.1)
    assert pending, "demo should produce a pending approval"
    p = pending[0]

    assert "APPROVED" in console.decide(p["action_id"], p["token"], "approve")

    final = None
    for _ in range(50):
        text = console.events_text(run_id)
        if '"FINAL"' in text:
            final = text
            break
        time.sleep(0.1)
    assert final and '"done"' in final
