"""Command-line entrypoint for the coding agent harness."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.config import HarnessConfig, load_config
from cah.credentials.manager import CredentialsManager
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.path import PathGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.guardrails.tool import ToolGuardrail
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.deepseek import DeepSeekLLM, LLMError
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop
from cah.memory.store import MemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cah", description="Coding Agent Harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run an agent task")
    p_run.add_argument("task", nargs="?")
    p_run.add_argument("--mock", action="store_true", help="use a scripted mock LLM")
    p_run.add_argument("--script", help="path to a mock LLM script (JSONL)")
    p_run.add_argument("--read-only", action="store_true", help="forbid writes")
    p_run.add_argument("--auto-approve", action="store_true", help="auto-approve HITL")
    p_run.add_argument("--workspace", default=".", help="workspace root")

    for cmd in ("approve", "reject"):
        p = sub.add_parser(cmd, help=f"{cmd} a pending action")
        p.add_argument("action_id")
        p.add_argument("--token", required=True, help="one-time approval token")
        p.add_argument("--workspace", default=".", help="workspace root")

    p_status = sub.add_parser("status", help="show pending approvals")
    p_status.add_argument("--workspace", default=".", help="workspace root")

    p_key = sub.add_parser("key", help="manage API keys")
    p_key.add_argument("action", choices=["set", "status", "clear"])

    p_cfg = sub.add_parser("config", help="manage configuration")
    p_cfg.add_argument("action", choices=["init", "show"])
    p_cfg.add_argument("--workspace", default=".", help="workspace root")

    sub.add_parser("demo", help="run the mechanism demo")
    return parser


def _workspace_root(path: str) -> Path:
    return Path(path).resolve()


def _harness_dir(workspace: Path) -> Path:
    return workspace / ".harness"


def _hitl(workspace: Path, timeout_s: int = 300) -> HITLStateMachine:
    return HITLStateMachine(_harness_dir(workspace) / "approvals.json", timeout_s=timeout_s)


def _load_or_default(workspace: Path) -> HarnessConfig:
    cfg_path = workspace / "harness.toml"
    if cfg_path.exists():
        return load_config(cfg_path)
    return HarnessConfig()


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.task:
        print("error: a task is required: cah run <task>", file=sys.stderr)
        return 2
    workspace = _workspace_root(args.workspace)
    config = _load_or_default(workspace)
    read_only = args.read_only or config.read_only

    sandbox = WorkspaceSandbox(workspace, read_only=read_only)
    tools = ToolRegistry(sandbox=sandbox)
    enabled = config.tools_enabled or tools.names()
    pipeline = GuardrailPipeline(
        [
            CommandGuardrail(config.deny_patterns, config.allow_prefixes),
            PathGuardrail(),
            ToolGuardrail(enabled, read_only=read_only),
        ]
    )
    hitl = _hitl(workspace, config.approval_timeout_s)
    memory = MemoryStore(_harness_dir(workspace) / "memory.json") if config.memory_enabled else None

    if args.mock:
        if args.script:
            script_path = Path(args.script)
        else:
            script_path = _harness_dir(workspace) / "default-mock.jsonl"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(
                json.dumps({"text": "mock run complete", "action": None, "done": True}) + "\n",
                encoding="utf-8",
            )
        llm = MockLLM(script_path)
    else:
        key = CredentialsManager().get_key()
        if not key:
            print("error: no API key configured; run `cah key set` first", file=sys.stderr)
            return 2
        llm = DeepSeekLLM(api_key=key, model=config.model)

    resolver = (lambda i, t: "approved") if args.auto_approve else (lambda i, t: "rejected")
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        pipeline=pipeline,
        hitl=hitl,
        validator=None,
        memory=memory,
        workspace=workspace,
        max_steps=config.max_steps,
        max_retries=config.max_retries,
        approval_resolver=resolver,
    )
    try:
        result = loop.run(args.task)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for event in result.actions_log:
        print(f"[{event.get('step', '?')}] {event.get('event', '?')}: {event.get('reason', '')}")
    print(f"status={result.status}")
    if result.final_output:
        print(result.final_output[:2000])
    return 0 if result.status == "done" else 1


def _cmd_decide(args: argparse.Namespace, approve: bool) -> int:
    workspace = _workspace_root(args.workspace)
    sm = _hitl(workspace)
    try:
        record = (
            sm.approve(args.action_id, args.token, "cli")
            if approve
            else sm.reject(args.action_id, args.token, "cli")
        )
    except (KeyError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"action={record.action_id} state={record.state}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    workspace = _workspace_root(args.workspace)
    sm = _hitl(workspace)
    pending = sm.list_pending()
    if not pending:
        print("no pending approvals")
        return 0
    for rec in pending:
        print(f"{rec.action_id}\t{rec.reason}\tcreated={rec.created_at:.0f}")
    return 0


def _cmd_key(args: argparse.Namespace) -> int:
    mgr = CredentialsManager()
    if args.action == "set":
        value = getpass.getpass("API key (hidden input): ")
        if not value:
            print("error: empty key", file=sys.stderr)
            return 1
        source = mgr.set_key(value)
        print(f"stored via {source}")
    elif args.action == "status":
        st = mgr.status()
        print(f"configured={st['configured']} source={st['source']} masked={st['masked']}")
    elif args.action == "clear":
        mgr.clear()
        print("key cleared")
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    workspace = _workspace_root(args.workspace)
    cfg_path = workspace / "harness.toml"
    if args.action == "init":
        if cfg_path.exists():
            print(f"harness.toml already exists at {cfg_path}", file=sys.stderr)
            return 1
        template = (
            '# Coding Agent Harness configuration\n'
            'model = "deepseek-chat"\n'
            "max_steps = 10\n"
            "approval_timeout_s = 300\n"
            "max_retries = 3\n"
            'deny_patterns = ["rm -rf", "DROP DATABASE", "git push"]\n'
            'allow_prefixes = ["python -m pytest"]\n'
            'tools_enabled = []\n'
            'validators = []\n'
            'workspace = "."\n'
            "read_only = false\n"
            "memory_enabled = true\n"
        )
        cfg_path.write_text(template, encoding="utf-8")
        print(f"wrote {cfg_path}")
    else:
        config = _load_or_default(workspace)
        for k, v in config.__dict__.items():
            print(f"{k} = {v!r}")
    return 0


def _cmd_demo() -> int:
    try:
        from demo.mechanism_demo import main as demo_main
    except ImportError:
        print("demo not implemented yet (planned in Task 16)", file=sys.stderr)
        return 1
    return demo_main()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command in ("approve", "reject"):
        return _cmd_decide(args, approve=args.command == "approve")
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "key":
        return _cmd_key(args)
    if args.command == "config":
        return _cmd_config(args)
    if args.command == "demo":
        return _cmd_demo()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
