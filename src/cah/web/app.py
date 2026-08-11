"""FastAPI approval console with a scripted demo mode (mock LLM, read-only)."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from cah.web.console import DemoConsole

HTML_PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


class ApproveBody(BaseModel):
    token: str


def create_app(store_dir: str | Path, demo: bool = True) -> FastAPI:
    """Build the approval console app.

    Demo mode: ``POST /api/demo`` runs a scripted mock-LLM loop whose dangerous
    action waits for a human decision through this console.
    """

    store_dir = Path(store_dir)
    console = DemoConsole(store_dir)

    app = FastAPI(title="cah approval console")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return HTML_PAGE

    @app.get("/api/actions")
    def list_actions() -> list[dict]:
        out: list[dict] = []
        for p in console.pending():
            item: dict = {"action_id": p["action_id"], "reason": p["reason"]}
            if demo:
                item["token"] = p["token"]
                item["run_id"] = p["run_id"]
            out.append(item)
        return out

    @app.post("/api/actions/{action_id}/approve")
    def approve(action_id: str, body: ApproveBody) -> dict:
        result = console.decide(action_id, body.token, "approve")
        if result.startswith("error:"):
            return JSONResponse({"error": result[6:]}, status_code=400)
        action_id, state = result.split(" -> ")
        return {"action_id": action_id, "state": state}

    @app.post("/api/actions/{action_id}/reject")
    def reject(action_id: str, body: ApproveBody) -> dict:
        result = console.decide(action_id, body.token, "reject")
        if result.startswith("error:"):
            return JSONResponse({"error": result[6:]}, status_code=400)
        action_id, state = result.split(" -> ")
        return {"action_id": action_id, "state": state}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str) -> StreamingResponse:
        async def gen():
            seen = 0
            while True:
                evs = console.events(run_id)
                while seen < len(evs):
                    yield f"data: {json.dumps(evs[seen], ensure_ascii=False)}\n\n"
                    seen += 1
                if console.is_finished(run_id):
                    yield "event: FINAL\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/demo")
    def start_demo() -> JSONResponse:
        run_id = console.start_demo()
        return JSONResponse({"run_id": run_id}, status_code=202)

    return app


_store_dir = os.environ.get("CAH_STORE_DIR", ".harness-web")
try:
    app = create_app(store_dir=_store_dir, demo=os.environ.get("HARNESS_DEMO", "1") == "1")
except OSError:
    # fall back to a writable temp location instead of crashing at import
    app = create_app(
        store_dir=os.path.join(tempfile.gettempdir(), "cah-web"),
        demo=os.environ.get("HARNESS_DEMO", "1") == "1",
    )
