"""Deterministic tests for the web approval console (demo mode)."""

import time

from fastapi.testclient import TestClient

from cah.web.app import create_app


def test_index_and_actions(tmp_path):
    app = create_app(store_dir=tmp_path)
    c = TestClient(app)
    assert c.get("/").status_code == 200
    assert c.get("/api/actions").json() == []


def test_demo_run_and_approval_flow(tmp_path):
    app = create_app(store_dir=tmp_path)
    c = TestClient(app)
    r = c.post("/api/demo")
    assert r.status_code == 202

    actions = []
    for _ in range(30):
        actions = c.get("/api/actions").json()
        if actions:
            break
        time.sleep(0.1)
    assert actions, "demo should create a pending approval"
    aid = actions[0]["action_id"]
    token = actions[0]["token"]
    assert c.post(f"/api/actions/{aid}/approve", json={"token": token}).status_code == 200

    # the loop should converge after approval
    final = None
    for _ in range(50):
        evs = c.get(f"/api/runs/{actions[0]['run_id']}/events")
        final = evs.text
        if '"FINAL"' in final or '"status"' in final:
            break
        time.sleep(0.1)
    assert final and "done" in final.lower()
