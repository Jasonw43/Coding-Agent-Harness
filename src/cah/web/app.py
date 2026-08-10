"""FastAPI approval console with a scripted demo mode (mock LLM, read-only)."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop

HTML_PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


class ApproveBody(BaseModel):
    token: str


def create_app(store_dir: str | Path, demo: bool = True) -> FastAPI:
    """Build the approval console app.

    Demo mode: ``POST /api/demo`` runs a scripted mock-LLM loop whose dangerous
    action waits for a human decision through this console.
    """

    store_dir = Path(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)
    runs: dict[str, list[dict]] = {}
    finished: set[str] = set()
    tokens: dict[str, dict] = {}

    app = FastAPI(title="cah approval console")

    def hitl() -> HITLStateMachine:
        return HITLStateMachine(store_dir / "approvals.json", timeout_s=120)

    def run_demo(run_id: str) -> None:
        events: list[dict] = []
        runs[run_id] = events
        ws = store_dir / "demo-ws"
        ws.mkdir(exist_ok=True)
        sandbox = WorkspaceSandbox(ws, read_only=True)
        tools = ToolRegistry(sandbox=sandbox)
        pipeline = GuardrailPipeline([CommandGuardrail([], [])])
        sm = hitl()

        script = store_dir / "demo-script.jsonl"
        script.write_text(
            "\n".join(
                json.dumps(s)
                for s in [
                    {
                        "text": "I will deploy to production now",
                        "action": {
                            "type": "shell",
                            "params": {"command": "deploy --prod"},
                        },
                        "done": False,
                    },
                    {"text": "done", "action": None, "done": True},
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        llm = MockLLM(script)

        def resolver(action_id: str, token: str) -> str:
            tokens[action_id] = {"token": token, "run_id": run_id}
            deadline = time.time() + 120
            while time.time() < deadline:
                # re-read from disk each poll so external approvals are visible
                rec = hitl().get(action_id)
                if rec is None:
                    time.sleep(0.2)
                    continue
                if rec.state == "APPROVED":
                    return "approved"
                if rec.state in ("REJECTED", "EXPIRED", "CANCELED"):
                    return "rejected"
                time.sleep(0.2)
            return "rejected"

        loop = AgentLoop(
            llm=llm,
            tools=tools,
            pipeline=pipeline,
            hitl=sm,
            validator=None,
            memory=None,
            workspace=ws,
            max_steps=5,
            max_retries=0,
            approval_resolver=resolver,
            run_id=run_id,
        )
        result = loop.run("deploy the application safely")
        for event in result.actions_log:
            events.append(event)
        events.append({"event": "FINAL", "status": result.status})
        finished.add(run_id)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return HTML_PAGE

    @app.get("/api/actions")
    def list_actions() -> list[dict]:
        out: list[dict] = []
        for rec in hitl().list_pending():
            item: dict = {"action_id": rec.action_id, "reason": rec.reason}
            info = tokens.get(rec.action_id)
            if info is not None and demo:
                item["token"] = info["token"]
                item["run_id"] = info["run_id"]
            out.append(item)
        return out

    @app.post("/api/actions/{action_id}/approve")
    def approve(action_id: str, body: ApproveBody) -> dict:
        try:
            rec = hitl().approve(action_id, body.token, "web")
        except (KeyError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"action_id": rec.action_id, "state": rec.state}

    @app.post("/api/actions/{action_id}/reject")
    def reject(action_id: str, body: ApproveBody) -> dict:
        try:
            rec = hitl().reject(action_id, body.token, "web")
        except (KeyError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"action_id": rec.action_id, "state": rec.state}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str) -> StreamingResponse:
        async def gen():
            seen = 0
            while True:
                evs = runs.get(run_id, [])
                while seen < len(evs):
                    yield f"data: {json.dumps(evs[seen], ensure_ascii=False)}\n\n"
                    seen += 1
                if run_id in finished:
                    yield "event: FINAL\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/demo")
    def start_demo() -> JSONResponse:
        run_id = uuid4().hex[:8]
        threading.Thread(target=run_demo, args=(run_id,), daemon=True).start()
        return JSONResponse({"run_id": run_id}, status_code=202)

    return app


app = create_app(
    store_dir=os.environ.get("CAH_STORE_DIR", ".harness-web"),
    demo=os.environ.get("HARNESS_DEMO", "1") == "1",
)
