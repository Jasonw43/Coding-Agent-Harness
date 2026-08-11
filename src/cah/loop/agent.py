"""Agent main loop: context -> LLM -> action -> guardrails -> tools -> feedback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable
from uuid import uuid4

from cah.actions.registry import ToolRegistry
from cah.actions.parser import parse_action
from cah.feedback.validators import Validator
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.base import LLMClient
from cah.memory.store import MemoryStore
from cah.models import Feedback, LLMResponse, RunResult

ApprovalResolver = Callable[[str, str], str]


class ValidationState(str, Enum):
    """Outcome of the previous validation run."""

    UNKNOWN = "unknown"
    FAILED = "failed"
    OK = "ok"


@dataclass
class HarnessContext:
    """Groups the AgentLoop dependencies to keep construction readable."""

    llm: LLMClient
    tools: ToolRegistry
    pipeline: GuardrailPipeline
    workspace: Path
    hitl: HITLStateMachine | None = None
    validator: Validator | None = None
    memory: MemoryStore | None = None
    max_steps: int = 10
    max_retries: int = 3
    approval_resolver: ApprovalResolver | None = None
    run_id: str | None = None
    context_budget_tokens: int = 16000


class AgentLoop:
    """Run a task through the harness: finite, deterministic, self-correcting."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        pipeline: GuardrailPipeline,
        hitl: HITLStateMachine | None,
        validator: Validator | None,
        memory: MemoryStore | None,
        workspace: Path,
        max_steps: int = 10,
        max_retries: int = 3,
        approval_resolver: ApprovalResolver | None = None,
        run_id: str | None = None,
        context_budget_tokens: int = 16000,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.pipeline = pipeline
        self.hitl = hitl
        self.validator = validator
        self.memory = memory
        self.workspace = Path(workspace)
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.approval_resolver = approval_resolver or (lambda i, t: "rejected")
        self._run_id = run_id
        self._final_text = ""
        self.context_budget_tokens = context_budget_tokens

    @classmethod
    def from_context(cls, ctx: HarnessContext) -> "AgentLoop":
        return cls(
            llm=ctx.llm,
            tools=ctx.tools,
            pipeline=ctx.pipeline,
            hitl=ctx.hitl,
            validator=ctx.validator,
            memory=ctx.memory,
            workspace=ctx.workspace,
            max_steps=ctx.max_steps,
            max_retries=ctx.max_retries,
            approval_resolver=ctx.approval_resolver,
            run_id=ctx.run_id,
            context_budget_tokens=ctx.context_budget_tokens,
        )

    # ---- context ----

    def _build_context(self, task: str, events: list[str]) -> list[dict]:
        context: list[dict] = [
            {
                "role": "system",
                "content": (
                    "You are a coding agent running inside a harness. "
                    "To use a tool, reply ONLY with a JSON object like "
                    '{"action": {"type": "write_file", "params": {"path": "a.txt", "content": "x"}}}. '
                    "NEVER paste code or file contents in your reply; file contents "
                    "go inside the action params. "
                    "When the task is complete, reply with plain text (your final answer). "
                    f"Available tools: {', '.join(self.tools.names())}. "
                    "You may receive feedback about failed validations; adjust accordingly."
                ),
            },
            {"role": "user", "content": task},
        ]
        if self.memory is not None:
            recalled = self.memory.recall(task)
            if recalled:
                context.append(
                    {
                        "role": "system",
                        "content": "Relevant memory:\n"
                        + "\n".join(f"- {e.key}: {e.content}" for e in recalled),
                    }
                )
        # keep the newest events that fit the context budget; truncate the rest
        budget = self.context_budget_tokens
        used = sum(self._approx_tokens(str(m.get("content", ""))) for m in context)
        kept: list[str] = []
        for event in reversed(events[-50:]):
            cost = self._approx_tokens(event)
            if used + cost > budget:
                kept.append("(earlier events truncated to fit the context budget)")
                break
            kept.append(event)
            used += cost
        for event in reversed(kept):
            context.append({"role": "user", "content": event})
        return context

    @staticmethod
    def _approx_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    # ---- run ----

    def run(self, task: str) -> RunResult:
        run_id = self._run_id or uuid4().hex[:8]
        events: list[dict] = []
        event_texts: list[str] = []
        retries = 0
        prev: ValidationState = ValidationState.UNKNOWN
        status = "failed"

        for step in range(1, self.max_steps + 1):
            context = self._build_context(task, event_texts)
            try:
                response: LLMResponse = self.llm.complete(
                    context, available_actions=self.tools.names()
                )
            except StopIteration:
                events.append({"step": step, "event": "STOP", "reason": "script exhausted"})
                break

            if response.actions:
                actions = response.actions
            elif response.action is not None:
                actions = [response.action]
            elif response.done:
                # mock-style structured completion
                status, retries = self._decide_done(
                    response.text, retries, events, event_texts, step
                )
                if status == "continue":
                    continue
                break
            else:
                # real-LLM text: parse the tool protocol
                parsed = parse_action(response.text, self.tools.names())
                if parsed.error is not None:
                    if retries >= self.max_retries:
                        status = "failed"
                        events.append(
                            {"step": step, "event": "FAILED", "summary": parsed.error}
                        )
                        break
                    retries += 1
                    self._push_feedback(
                        Feedback(ok=False, failures=[parsed.error], summary="action format error"),
                        event_texts,
                        events,
                        step,
                    )
                    continue
                if parsed.done:
                    status, retries = self._decide_done(
                        parsed.answer or response.text, retries, events, event_texts, step
                    )
                    if status == "continue":
                        continue
                    break
                actions = parsed.actions

            executed_any = False
            for action in actions:
                if not action.id:
                    action.id = f"{run_id}-s{step}"
                action.run_id = run_id

                decision = self.pipeline.check(action, self.workspace)

                if decision.verdict == "BLOCKED":
                    msg = f"BLOCKED: {decision.reason} (action={action.id})"
                    event_texts.append(msg)
                    events.append(
                        {
                            "step": step,
                            "event": "BLOCKED",
                            "reason": decision.reason,
                            "action": action.id,
                        }
                    )
                    continue

                if decision.verdict == "REQUIRE_APPROVAL":
                    if self.hitl is None:
                        msg = f"REJECTED: no approval channel (action={action.id})"
                        event_texts.append(msg)
                        events.append({"step": step, "event": "REJECTED", "action": action.id})
                        continue
                    record, token = self.hitl.submit(action.id, decision.reason)
                    if self.approval_resolver(action.id, token) != "approved":
                        msg = f"REJECTED by user: {decision.reason} (action={action.id})"
                        event_texts.append(msg)
                        events.append({"step": step, "event": "REJECTED", "action": action.id})
                        continue
                    # approved: fall through to execute the action

                result = self.tools.dispatch(action.type, action.params)
                executed_any = True
                event_texts.append(
                    f"TOOL {action.type} -> ok={result.ok}: {result.output[:500]}"
                )
                events.append(
                    {"step": step, "event": "TOOL", "tool": action.type, "ok": result.ok}
                )

            if not executed_any:
                # nothing ran this step (blocked/rejected): no new feedback
                continue

            # feedback loop: validate after the action
            fb = self._validate()
            if fb is not None and not fb.ok:
                if retries >= self.max_retries:
                    status = "failed"
                    events.append({"step": step, "event": "FAILED", "summary": fb.summary})
                    break
                retries += 1
                self._push_feedback(fb, event_texts, events, step)
                prev = ValidationState.FAILED
                continue

            if prev is ValidationState.FAILED:
                # a previous failure is now fixed -> converged
                status = "done"
                events.append(
                    {"step": step, "event": "DONE", "reason": "validation converged"}
                )
                break
            prev = ValidationState.OK

        return RunResult(
            run_id=run_id,
            status=status,
            steps=len(events),
            actions_log=events,
            final_output=self._final_text or (event_texts[-1] if event_texts else ""),
        )

    # ---- helpers ----

    def _validate(self) -> Feedback | None:
        if self.validator is None:
            return None
        return self.validator.validate(self.workspace)

    def _push_feedback(
        self, fb: Feedback, event_texts: list[str], events: list[dict], step: int
    ) -> None:
        event_texts.append(f"FEEDBACK: {fb.summary}\n" + failures_text(fb))
        events.append({"step": step, "event": "FEEDBACK", "summary": fb.summary})

    def _decide_done(
        self,
        final_text: str,
        retries: int,
        events: list[dict],
        event_texts: list[str],
        step: int,
    ) -> tuple[str, int]:
        """Validate on completion; returns (status, updated retries)."""
        fb = self._validate()
        if fb is None or fb.ok:
            events.append({"step": step, "event": "DONE"})
            self._final_text = final_text
            return "done", retries
        if retries >= self.max_retries:
            events.append({"step": step, "event": "FAILED", "summary": fb.summary})
            return "failed", retries
        retries += 1
        self._push_feedback(fb, event_texts, events, step)
        return "continue", retries


def failures_text(fb: Feedback) -> str:
    return "\n".join(f"- {line}" for line in fb.failures)
