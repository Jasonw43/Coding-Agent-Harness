# Coding Agent Harness (`cah`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Python 实现一个治理优先的 coding agent harness——本地 CLI 运行、浏览器审批台完成 HITL、线上 mock 演示实例，且全部核心机制在移除真实 LLM 后仍可确定性单测。

**Architecture:** 分层内核 + 薄 Web 壳。`loop` 主循环依赖 `llm` 抽象（mock/deepseek）、`guardrails` 决策管线、`hitl` 审批状态机、`actions` 工具沙箱、`feedback` 校验器、`memory` 记忆、`config` 配置；`cli` 与 `web` 是两个入口；`credentials` 提供 key 安全存取。

**Tech Stack:** Python 3.11–3.13（开发/CI 固定 3.12）、pytest、httpx、FastAPI + uvicorn、keyring、hatchling。

**文件结构（实现前锁定）：**

```
pyproject.toml                  # 打包 + 依赖 + cah 命令入口
README.md                       # 课程要求章节
.gitlab-ci.yml                  # unit-test job（NJU GitLab）
.github/workflows/ci.yml        # GitHub Actions 实际 CI
src/cah/
  models.py                     # Action/ToolResult/GuardrailDecision/Feedback/LLMResponse/RunResult/ApprovalRecord
  config.py                     # HarnessConfig + TOML 加载校验
  llm/{base,mock,deepseek}.py   # LLMClient 协议、MockLLM(JSONL)、DeepSeekLLM(httpx)
  loop/agent.py                 # AgentLoop 主循环
  actions/{sandbox,registry,tools}.py
  guardrails/{command,path,tool,pipeline}.py
  hitl/state_machine.py         # HITL 状态机 + JSON 持久化
  feedback/validators.py        # Validator 协议 + TestRunnerValidator
  memory/store.py               # MemoryStore + SessionMemory
  credentials/manager.py        # keyring + .env 兜底
  cli.py                        # argparse 命令面
  web/app.py                    # FastAPI + 单页 UI
tests/                          # 每个模块对应 test_*.py，全部 mock 驱动
demo/mechanism_demo.py          # 三行为机制演示
```

**依赖与并行批次（用于 worktree）：**

- T01 → T02 串行（骨架 → 核心类型）。
- Batch A（T01/T02 后并行）：T03 配置、T04 LLM、T05 命令护栏、T06 路径护栏、T09 工具沙箱、T10 记忆、T11 校验器、T12 凭据。
- Batch B：T07 护栏管线（依赖 T05/T06）→ T08 HITL（依赖 T07）。
- Batch C（集成，依赖 A+B）：T13 主循环 → T14 CLI、T15 Web、T16 机制演示（可并行）。
- Batch D（交付）：T17 README、T18 CI、T19 打包、T20 部署配置（可并行）。

---

### Task 1: 项目骨架

**Files:**
- Create: `pyproject.toml`
- Create: `src/cah/__init__.py`、`src/cah/llm/__init__.py`、`src/cah/loop/__init__.py`、`src/cah/actions/__init__.py`、`src/cah/guardrails/__init__.py`、`src/cah/hitl/__init__.py`、`src/cah/feedback/__init__.py`、`src/cah/memory/__init__.py`、`src/cah/credentials/__init__.py`、`src/cah/web/__init__.py`（空文件，包标记）
- Create: `tests/conftest.py`、`tests/test_import.py`

- [ ] **Step 1: 写失败测试** `tests/test_import.py`

```python
def test_cah_importable():
    import cah
    assert cah.__name__ == "cah"
```

- [ ] **Step 2: 验证失败**
Run: `python -m pytest tests/test_import.py -v` → 预期 `ModuleNotFoundError: cah`

- [ ] **Step 3: 最小实现** — 创建 `pyproject.toml`（requires-python `>=3.11,<3.14`，hatchling 打包，`[project.scripts] cah = "cah.cli:main"`，依赖 httpx/fastapi/uvicorn/keyring，dev 依赖 pytest/httpx）与全部空包文件；`src/cah/__init__.py` 写 `__version__ = "0.1.0"`。

- [ ] **Step 4: 验证通过** — `python -m pytest tests/test_import.py -v` → PASS

- [ ] **Step 5: 提交** — `git add pyproject.toml src tests && git commit -m "chore: scaffold cah package"`

### Task 2: 核心类型 `models.py`

**Files:**
- Create: `src/cah/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败测试** `tests/test_models.py`

```python
from cah.models import Action, ToolResult, GuardrailDecision, Feedback, LLMResponse, RunResult

def test_action_fields():
    a = Action(id="a1", type="shell", params={"command": "pwd"}, run_id="r1")
    assert a.type == "shell" and a.params["command"] == "pwd"

def test_guardrail_decision_defaults():
    d = GuardrailDecision(verdict="SAFE")
    assert d.reason == "" and d.risk_level == "low"

def test_run_result_status_default():
    r = RunResult(run_id="r1", status="running", steps=0, actions_log=[], final_output="")
    assert r.status == "running"

def test_feedback_and_llm_response():
    fb = Feedback(ok=False, failures=["FAILED test_x"], summary="1 failed")
    resp = LLMResponse(text="t", action=None, done=True)
    assert not fb.ok and resp.done
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_models.py -v` → `ModuleNotFoundError`

- [ ] **Step 3: 最小实现** — 定义 dataclass：`Action(id, type, params, run_id)`；`ToolResult(ok, output, meta)`；`GuardrailDecision(verdict, reason="", risk_level="low", action_id="")`；`Feedback(ok, failures, summary)`；`LLMResponse(text, action, done)`；`RunResult(run_id, status, steps, actions_log, final_output)`。

- [ ] **Step 4: 验证通过** — `pytest tests/test_models.py -v` → 4 PASS

- [ ] **Step 5: 提交** — `git add src/cah/models.py tests/test_models.py && git commit -m "feat: core data models"`

### Task 3: 配置 `config.py`

**Files:**
- Create: `src/cah/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试** `tests/test_config.py`

```python
import tomllib
from pathlib import Path
from cah.config import HarnessConfig, load_config

def test_load_valid_toml(tmp_path):
    p = tmp_path / "harness.toml"
    p.write_text('model = "mock"\nmax_steps = 5\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.model == "mock" and cfg.max_steps == 5

def test_invalid_config_fails_fast(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('model = "mock"\nmax_steps = "not-int"\n', encoding="utf-8")
    try:
        load_config(p)
        assert False, "should raise"
    except ValueError:
        pass
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_config.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `HarnessConfig` dataclass：`model="mock", max_steps=10, approval_timeout_s=300, max_retries=3, deny_patterns=[], allow_prefixes=[], tools_enabled=[], validators=[], workspace=".", read_only=False, memory_enabled=True`；`load_config(path)` 用 `tomllib.load`，逐字段类型校验，非法即 `raise ValueError(定位信息)`；缺省字段用默认值。

- [ ] **Step 4: 验证通过** — `pytest tests/test_config.py -v` → 2 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: declarative TOML config"`

### Task 4: LLM 抽象与 MockLLM

**Files:**
- Create: `src/cah/llm/base.py`、`src/cah/llm/mock.py`
- Test: `tests/test_llm_mock.py`

- [ ] **Step 1: 写失败测试** `tests/test_llm_mock.py`

```python
import json
from cah.llm.mock import MockLLM

def test_mock_llm_scripted_steps(tmp_path):
    script = [
        {"text": "read a file", "action": {"type": "read_file", "params": {"path": "a.txt"}}, "done": False},
        {"text": "finished", "action": None, "done": True},
    ]
    p = tmp_path / "script.jsonl"
    p.write_text("\n".join(json.dumps(s) for s in script), encoding="utf-8")
    llm = MockLLM(script_path=p)
    r1 = llm.complete(context=[], available_actions=[])
    assert r1.action.type == "read_file" and not r1.done
    r2 = llm.complete(context=[], available_actions=[])
    assert r2.done and r2.action is None

def test_mock_llm_exhausts(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text('{"text":"only one","action":null,"done":true}\n', encoding="utf-8")
    llm = MockLLM(script_path=p)
    llm.complete(context=[], available_actions=[])
    try:
        llm.complete(context=[], available_actions=[])
        assert False, "should raise"
    except StopIteration:
        pass
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_llm_mock.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `base.py`：`LLMClient` Protocol：`complete(context: list[dict], available_actions: list[dict]) -> LLMResponse`。`mock.py`：`MockLLM(script_path, loop=False)`，内部游标逐行读 JSONL，构造 `LLMResponse`；超出步数 `raise StopIteration`。

- [ ] **Step 4: 验证通过** — `pytest tests/test_llm_mock.py -v` → 2 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: LLM abstraction with scripted mock"`

### Task 5: 命令护栏 `guardrails/command.py`

**Files:**
- Create: `src/cah/guardrails/command.py`
- Test: `tests/test_guardrails.py`

- [ ] **Step 1: 写失败测试**（加入 `tests/test_guardrails.py`）

```python
from pathlib import Path
from cah.models import Action
from cah.guardrails.command import CommandGuardrail

def test_blocks_rm_rf():
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=["python -m pytest"])
    d = g.check(Action(id="a", type="shell", params={"command": "rm -rf /"}, run_id="r"), Path("."))
    assert d.verdict == "BLOCKED"

def test_allows_test_command():
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=["python -m pytest"])
    d = g.check(Action(id="a", type="shell", params={"command": "python -m pytest tests"}, run_id="r"), Path("."))
    assert d.verdict == "SAFE"

def test_non_shell_action_safe():
    g = CommandGuardrail(deny_patterns=[], allow_prefixes=[])
    d = g.check(Action(id="a", type="read_file", params={"path": "x"}, run_id="r"), Path("."))
    assert d.verdict == "SAFE"
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_guardrails.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `CommandGuardrail(deny_patterns, allow_prefixes)`；`check(action, workspace)`：非 `shell` 动作直接 SAFE；命令 `shlex.split` 后 join；命中任一 deny 子串 → `BLOCKED`；否则命中任一 allow 前缀 → `SAFE`；其余默认 `REQUIRE_APPROVAL`（保守）。返回 `GuardrailDecision`（含 reason）。

- [ ] **Step 4: 验证通过** — `pytest tests/test_guardrails.py -v` → 3 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: command guardrail"`

### Task 6: 路径护栏 `guardrails/path.py`

**Files:**
- Create: `src/cah/guardrails/path.py`
- Test: `tests/test_guardrails.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
from cah.guardrails.path import PathGuardrail

def test_path_escape_blocked(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    g = PathGuardrail()
    d = g.check(Action(id="a", type="write_file", params={"path": "../outside.txt"}, run_id="r"), ws)
    assert d.verdict == "BLOCKED"

def test_path_inside_ok(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    g = PathGuardrail()
    d = g.check(Action(id="a", type="write_file", params={"path": "ok.txt"}, run_id="r"), ws)
    assert d.verdict == "SAFE"
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_guardrails.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `PathGuardrail.check(action, workspace)`：对 `read_file/write_file` 类动作，`(workspace / path).resolve()` 与 `workspace.resolve()` 比较，前缀不匹配 → `BLOCKED`；非文件类动作 SAFE。

- [ ] **Step 4: 验证通过** — `pytest tests/test_guardrails.py -v` → 5 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: path confinement guardrail"`

### Task 7: 工具护栏与管线 `guardrails/tool.py` + `pipeline.py`

**Files:**
- Create: `src/cah/guardrails/tool.py`、`src/cah/guardrails/pipeline.py`
- Test: `tests/test_guardrails.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
from cah.guardrails.tool import ToolGuardrail
from cah.guardrails.pipeline import GuardrailPipeline

def test_tool_disabled_blocked():
    g = ToolGuardrail(tools_enabled=["read_file"], read_only=False)
    d = g.check(Action(id="a", type="shell", params={}, run_id="r"), None)
    assert d.verdict == "BLOCKED"

def test_pipeline_first_non_safe_wins():
    from cah.guardrails.command import CommandGuardrail
    from cah.guardrails.path import PathGuardrail
    from cah.models import Action
    p = GuardrailPipeline([
        PathGuardrail(),
        CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[]),
    ])
    d = p.check(Action(id="a", type="shell", params={"command": "rm -rf x"}, run_id="r"), Path("."))
    assert d.verdict == "BLOCKED"
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_guardrails.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `ToolGuardrail(tools_enabled, read_only)`：动作类型不在启用列表 → BLOCKED；`read_only` 且类型 ∈ {write_file, shell} → BLOCKED。`GuardrailPipeline(guards)`：按序 `check`，返回第一个非 SAFE；全 SAFE 返回 SAFE；任一检查器抛异常 → 返回 `BLOCKED(fail-closed)`。

- [ ] **Step 4: 验证通过** — `pytest tests/test_guardrails.py -v` → 7 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: tool guardrail and pipeline (fail-closed)"`

### Task 8: HITL 状态机 `hitl/state_machine.py`

**Files:**
- Create: `src/cah/hitl/state_machine.py`
- Test: `tests/test_hitl.py`

- [ ] **Step 1: 写失败测试** `tests/test_hitl.py`

```python
from cah.hitl.state_machine import HITLStateMachine

def test_full_transitions(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=300)
    rec, token = sm.submit(action_id="a1", reason="danger")
    assert rec.state == "PENDING" and token
    assert sm.approve("a1", token, "user").state == "APPROVED"
    assert sm.approve("a1", token, "user").state == "APPROVED"  # 幂等

def test_reject_and_expiry(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=-1)
    rec, token = sm.submit(action_id="a2", reason="danger")
    assert sm.reject("a2", token, "user").state == "REJECTED"
    rec2, _ = sm.submit(action_id="a3", reason="x")
    assert sm.resolve_expired()[0].state == "EXPIRED"

def test_wrong_token_rejected(tmp_path):
    sm = HITLStateMachine(store_path=tmp_path / "approvals.json", timeout_s=300)
    sm.submit(action_id="a4", reason="x")
    try:
        sm.approve("a4", "wrong", "user")
        assert False, "should raise"
    except PermissionError:
        pass
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_hitl.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `ApprovalRecord` dataclass + `ApprovalState` Enum（PENDING/APPROVED/REJECTED/EXPIRED/CANCELED）；`HITLStateMachine(store_path, timeout_s)`：`submit()` 生成 `secrets.token_urlsafe(16)` token（只返回一次），存 `sha256(token)`；`approve/reject` 校验 token 哈希，状态非 PENDING 时幂等返回；`resolve_expired()` 将超时项置 EXPIRED；JSON 文件持久化（原子写：先写临时文件再 rename）。

- [ ] **Step 4: 验证通过** — `pytest tests/test_hitl.py -v` → 3 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: HITL approval state machine"`

### Task 9: 工具沙箱与内置工具 `actions/`

**Files:**
- Create: `src/cah/actions/sandbox.py`、`src/cah/actions/registry.py`、`src/cah/actions/tools.py`
- Test: `tests/test_actions.py`

- [ ] **Step 1: 写失败测试** `tests/test_actions.py`

```python
from cah.actions.sandbox import WorkspaceSandbox
from cah.actions.registry import ToolRegistry

def test_write_read_file(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.write_file("hello.txt", "hi")
    assert r.ok and sb.read_file("hello.txt").output == "hi"

def test_write_escape_blocked(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.write_file("../evil.txt", "x")
    assert not r.ok

def test_shell_runs_in_workspace(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.run_shell("pwd", timeout_s=10)
    assert r.ok and str(tmp_path) in r.output

def test_registry_dispatch(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    reg = ToolRegistry(sandbox=sb)
    r = reg.dispatch("write_file", {"path": "a.txt", "content": "x"})
    assert r.ok
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_actions.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `WorkspaceSandbox(root, read_only)`：`resolve(path)` realpath 前缀校验（越界抛/返回错误）；`read_file/write_file/list_dir/run_shell`（subprocess，`cwd=root`，`env` 过滤敏感变量，超时与输出上限 64KB，失败结构化）。`ToolRegistry(sandbox, memory)`：`register(name, fn)` + `dispatch(type, params) -> ToolResult`，未知工具返回 `ok=False`。`tools.py` 挂载 read_file/write_file/list_dir/search(rg)/shell/run_tests/memory_store/memory_recall。

- [ ] **Step 4: 验证通过** — `pytest tests/test_actions.py -v` → 4 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: workspace sandbox and tool registry"`

### Task 10: 记忆 `memory/store.py`

**Files:**
- Create: `src/cah/memory/store.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: 写失败测试** `tests/test_memory.py`

```python
from cah.memory.store import MemoryStore

def test_store_and_recall(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    ms.store("convention", "use pytest", tags=["testing"])
    hits = ms.recall("pytest")
    assert hits and hits[0].key == "convention"

def test_recall_empty(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    assert ms.recall("nothing") == []
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_memory.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `MemoryEntry(key, content, tags, created_at)`；`MemoryStore(path)`：JSON 列表持久化，`store()` 追加（去重同 key 覆盖），`recall(query, limit=5)` 按关键词/标签子串匹配返回片段；损坏文件 → 备份 `.bak` 后重建并记警告。

- [ ] **Step 4: 验证通过** — `pytest tests/test_memory.py -v` → 2 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: persistent memory store"`

### Task 11: 反馈校验器 `feedback/validators.py`

**Files:**
- Create: `src/cah/feedback/validators.py`
- Test: `tests/test_feedback.py`

- [ ] **Step 1: 写失败测试** `tests/test_feedback.py`

```python
from cah.feedback.validators import TestRunnerValidator

def test_validator_reports_failure(tmp_path):
    v = TestRunnerValidator(command=["python", "-c", "raise SystemExit(1)"])
    fb = v.validate(tmp_path)
    assert not fb.ok and any("failed" in f.lower() for f in fb.failures)

def test_validator_reports_success(tmp_path):
    v = TestRunnerValidator(command=["python", "-c", "pass"])
    fb = v.validate(tmp_path)
    assert fb.ok
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_feedback.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `Validator` Protocol：`validate(workspace) -> Feedback`；`TestRunnerValidator(command, timeout_s=120)`：subprocess 运行，`returncode==0` → ok；否则解析 stderr/stdout 中含 `FAILED`/`Error` 的行作为 failures，summary 为退出码 + 行数；超时 → `ok=False`。

- [ ] **Step 4: 验证通过** — `pytest tests/test_feedback.py -v` → 2 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: deterministic feedback validators"`

### Task 12: 凭据管理 `credentials/manager.py`

**Files:**
- Create: `src/cah/credentials/manager.py`
- Test: `tests/test_credentials.py`

- [ ] **Step 1: 写失败测试** `tests/test_credentials.py`

```python
import pytest
from cah.credentials.manager import CredentialsManager

@pytest.fixture
def mgr(monkeypatch, tmp_path):
    store = {}
    monkeypatch.setattr("cah.credentials.manager.keyring", _FakeKeyring(store))
    return CredentialsManager(service="test", env_file=tmp_path / ".env")

def test_set_status_clear(mgr):
    mgr.set_key("sk-123")
    st = mgr.status()
    assert st["configured"] and "sk-123" not in st["masked"]
    assert mgr.get_key() == "sk-123"
    mgr.clear()
    assert not mgr.status()["configured"]

class _FakeKeyring:
    def __init__(self, store): self.store = store
    def get_password(self, s, u): return self.store.get((s, u))
    def set_password(self, s, u, p): self.store[(s, u)] = p
    def delete_password(self, s, u): self.store.pop((s, u), None)
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_credentials.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `CredentialsManager(service="cah", env_prefix="CAH", env_file=Path(".env"))`：`set_key()` 写 keyring（失败回退 .env，记警告）；`get_key()` 顺序 keyring → 环境变量 → .env；`status()` 返回 `{"configured": bool, "source": str, "masked": "sk-****"}`；`clear()` 清除全部来源。读 .env 用简单解析（`KEY=VALUE` 行），**不回显明文**。

- [ ] **Step 4: 验证通过** — `pytest tests/test_credentials.py -v` → 1 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: credentials manager (keyring first)"`

### Task 13: 主循环 `loop/agent.py`

**Files:**
- Create: `src/cah/loop/agent.py`
- Test: `tests/test_loop.py`

- [ ] **Step 1: 写失败测试** `tests/test_loop.py`

```python
import json
from pathlib import Path
from cah.loop.agent import AgentLoop
from cah.llm.mock import MockLLM
from cah.actions.sandbox import WorkspaceSandbox
from cah.actions.registry import ToolRegistry
from cah.guardrails.pipeline import GuardrailPipeline
from cah.guardrails.command import CommandGuardrail
from cah.hitl.state_machine import HITLStateMachine
from cah.feedback.validators import TestRunnerValidator
from cah.memory.store import MemoryStore

def _make_loop(tmp_path, script, approval="approve"):
    sp = tmp_path / "script.jsonl"
    sp.write_text("\n".join(json.dumps(s) for s in script), encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    return AgentLoop(
        llm=MockLLM(sp),
        tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
        pipeline=GuardrailPipeline([CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[])]),
        hitl=HITLStateMachine(tmp_path / "approvals.json", timeout_s=300),
        validator=TestRunnerValidator(["python", "-c", "pass"]),
        memory=MemoryStore(tmp_path / "memory.json"),
        workspace=ws, max_steps=5, max_retries=1, approval_resolver=lambda i, t: approval,
    )

def test_loop_runs_to_done(tmp_path):
    loop = _make_loop(tmp_path, [
        {"text": "done", "action": None, "done": True},
    ])
    r = loop.run("task")
    assert r.status == "done"

def test_loop_blocks_dangerous_action(tmp_path):
    loop = _make_loop(tmp_path, [
        {"text": "rm", "action": {"type": "shell", "params": {"command": "rm -rf /"}}, "done": False},
        {"text": "done", "action": None, "done": True},
    ])
    r = loop.run("task")
    assert any("BLOCKED" in str(e) or "blocked" in str(e) for e in r.actions_log)

def test_loop_hits_max_steps(tmp_path):
    loop = _make_loop(tmp_path, [
        {"text": "again", "action": {"type": "read_file", "params": {"path": "a.txt"}}, "done": False},
        {"text": "again", "action": {"type": "read_file", "params": {"path": "a.txt"}}, "done": False},
    ])
    r = loop.run("task")
    assert r.status == "failed" and r.steps >= 2

def test_feedback_changes_next_action(tmp_path):
    # 校验器先失败一次，第二次调用通过；断言 mock 收到失败反馈后动作改变
    calls = {"n": 0}
    class Flaky:
        def validate(self, ws):
            calls["n"] += 1
            return _FB(ok=calls["n"] > 1)
    loop = _make_loop(tmp_path, [
        {"text": "write", "action": {"type": "write_file", "params": {"path": "x.py", "content": "1"}}, "done": False},
        {"text": "write again", "action": {"type": "write_file", "params": {"path": "x.py", "content": "2"}}, "done": False},
    ])
    loop.validator = Flaky()
    r = loop.run("task")
    assert r.status == "done"
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_loop.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `AgentLoop(...)`：
  - 构造函数中 `hitl` 与 `validator` 允许为 `None`（分别对应"无人工审批"与"不跑校验器"的配置）；
  - 上下文组装：system（配置摘要）→ user（任务）→ memory 召回 → 历史事件（含反馈）→ 当前步；
  - 每步调 `llm.complete`，解析 `action`：
    - `done/None` → 跑 validator（若配置），ok → `status="done"`；失败且 `retries < max_retries` → 反馈入上下文继续，否则 `failed`；
    - 有 action → `pipeline.check`：SAFE → 工具分发，结果入日志与上下文；REQUIRE_APPROVAL → `hitl.submit` 后用 `approval_resolver(action_id, token)` 取决策（approve → 执行；reject → 回灌"REJECTED: reason"）；BLOCKED → 回灌 "BLOCKED: reason"；
  - 步数超 `max_steps` → `failed`；事件全部入 `RunResult.actions_log`；任何未捕获异常 → `failed`（结构化）。

- [ ] **Step 4: 验证通过** — `pytest tests/test_loop.py -v` → 4 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: agent main loop with guardrails and feedback"`

### Task 14: CLI `cli.py`

**Files:**
- Create: `src/cah/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试** `tests/test_cli.py`

```python
from cah.cli import build_parser

def test_parser_commands():
    p = build_parser()
    for cmd in ["run", "approve", "reject", "status", "key", "config", "demo"]:
        args = p.parse_args([cmd])
        assert args.command == cmd
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_cli.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `build_parser()`：argparse 子命令 `run <task>`（`--mock`、`--read-only`、`--workspace`）、`approve <action_id>`、`reject <action_id>`、`status`、`key set|status|clear`（set 用 `getpass` 隐藏输入）、`config init|show`（init 生成默认 TOML）、`demo`。`main(argv=None)` 分发；退出码 0/非 0。

- [ ] **Step 4: 验证通过** — `pytest tests/test_cli.py -v` → 1 PASS；再手动 `python -m cah.cli --help` 冒烟

- [ ] **Step 5: 提交** — `git commit -am "feat: CLI entrypoint"`

### Task 15: Web 审批台 `web/app.py`

**Files:**
- Create: `src/cah/web/app.py`、`src/cah/web/static/index.html`（内联 CSS/JS 单页）
- Test: `tests/test_web.py`

- [ ] **Step 1: 写失败测试** `tests/test_web.py`

```python
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
    # 等待后台任务产生待审动作（轮询最多 2s）
    actions = []
    for _ in range(20):
        actions = c.get("/api/actions").json()
        if actions:
            break
        import time; time.sleep(0.1)
    assert actions, "demo should create a pending approval"
    aid = actions[0]["action_id"]
    assert c.post(f"/api/actions/{aid}/approve", json={"token": actions[0]["token"]}).status_code == 200
```

- [ ] **Step 2: 验证失败** — `pytest tests/test_web.py -v` → 导入失败

- [ ] **Step 3: 最小实现** — `create_app(store_dir, demo=True)`：`GET /` 返回单页 UI；`GET /api/actions` 读 HITL 存储；`POST /api/actions/{id}/approve|reject` 调状态机；`GET /api/runs/{id}/events` SSE 心跳；`POST /api/demo` 后台线程跑一条 mock 脚本（含一个危险动作 → PENDING → 用户审批 → 完成），事件写入内存队列。demo 模式强制 MockLLM + 只读沙箱。

- [ ] **Step 4: 验证通过** — `pytest tests/test_web.py -v` → 2 PASS

- [ ] **Step 5: 提交** — `git commit -am "feat: web approval console (demo mode)"`

### Task 16: 机制演示 `demo/mechanism_demo.py`

**Files:**
- Create: `demo/mechanism_demo.py`
- Test: 通过脚本自身断言（`pytest` 之外的一键复现）

- [ ] **Step 1: 写演示脚本（含内置断言，相当于先写"测试"）**

```python
"""机制演示：确定性复现课程要求的三个行为。python demo/mechanism_demo.py"""
from cah.models import Action
from cah.guardrails.command import CommandGuardrail
from cah.hitl.state_machine import HITLStateMachine
from cah.loop.agent import AgentLoop
from cah.llm.mock import MockLLM
from cah.actions.sandbox import WorkspaceSandbox
from cah.actions.registry import ToolRegistry
from cah.guardrails.pipeline import GuardrailPipeline
from cah.feedback.validators import TestRunnerValidator
from cah.memory.store import MemoryStore
from cah.models import Feedback
from pathlib import Path
import tempfile
import json

def demo_1_guardrail_blocks():
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[])
    d = g.check(Action(id="a", type="shell", params={"command": "rm -rf /"}, run_id="r"), Path("."))
    assert d.verdict == "BLOCKED", d
    print("① 护栏拦截危险动作: BLOCKED ->", d.reason)

def demo_3_hitl_transitions():
    with tempfile.TemporaryDirectory() as td:
        sm = HITLStateMachine(Path(td) / "a.json", timeout_s=300)
        rec, token = sm.submit("a1", "危险命令")
        assert sm.reject("a1", token, "user").state == "REJECTED"
        print("③ HITL 状态机: PENDING -> REJECTED (其余转移见单测)")

def demo_2_feedback_changes_next_action():
    # 自包含实现：校验失败 → 反馈入上下文 → 动作重试后成功
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        sp = p / "script.jsonl"
        sp.write_text("\n".join(json.dumps(s) for s in [
            {"text": "write", "action": {"type": "write_file", "params": {"path": "x.py", "content": "1"}}, "done": False},
            {"text": "write again", "action": {"type": "write_file", "params": {"path": "x.py", "content": "2"}}, "done": False},
        ]), encoding="utf-8")
        ws = p / "ws"; ws.mkdir()
        loop = AgentLoop(
            llm=MockLLM(sp),
            tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
            pipeline=GuardrailPipeline([]),
            hitl=None,
            validator=None,
            memory=MemoryStore(p / "memory.json"),
            workspace=ws, max_steps=5, max_retries=1,
            approval_resolver=lambda i, t: "approve",
        )
        class Flaky:
            def __init__(self): self.n = 0
            def validate(self, ws):
                self.n += 1
                return Feedback(ok=self.n > 1, failures=[] if self.n > 1 else ["FAILED"], summary="flaky")
        loop.validator = Flaky()
        r = loop.run("task")
        assert r.status == "done"
        print("② 反馈闭环: 首次校验失败 -> 反馈回灌 -> 动作重试后 done")

if __name__ == "__main__":
    demo_1_guardrail_blocks(); demo_2_feedback_changes_next_action(); demo_3_hitl_transitions()
```

- [ ] **Step 2: 运行验证** — `python demo/mechanism_demo.py` → 三行输出、无异常、退出码 0

- [ ] **Step 3: 提交** — `git add demo/mechanism_demo.py && git commit -m "demo: mechanism demo (3 required behaviors)"`

### Task 17: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: 编写** — 必须含课程要求的章节：项目简介；安装（`pip install` 与 `pip install git+...`）；运行（`cah run --mock`、审批、`cah demo`）；key 安全配置（`cah key set`，Windows 凭据管理器，`.env` 明文风险说明）；分发（PyPI wheel 构建命令）；目录结构；安全边界（沙箱、只读模式、fail-closed）；已知限制（Python 3.11–3.13、Render 免费档休眠、demo 模式限制）；第三方依赖许可证声明。

- [ ] **Step 2: 自查** — 对照 SPEC §9 验收标准逐条可追溯到 README/命令

- [ ] **Step 3: 提交** — `git commit -am "docs: README with required sections"`

### Task 18: CI 双轨

**Files:**
- Create: `.github/workflows/ci.yml`、`.gitlab-ci.yml`

- [ ] **Step 1: 编写 GitHub Actions** — `on: [push, pull_request]`；job `test`：ubuntu-latest、setup-python 3.12、`pip install -e ".[dev]"`、`pytest`、`python -m build`；job `publish` 仅在 tag 触发时 `twine upload`（用 `PYPI_TOKEN` secret）。

- [ ] **Step 2: 编写 GitLab CI** — `.gitlab-ci.yml`：`image: python:3.12`；job 名**必须**为 `unit-test`：`pip install -e ".[dev]"` + `pytest` + `python -m build`。

- [ ] **Step 3: 本地验证等价命令** — `pip install -e ".[dev]" && pytest` → 全绿

- [ ] **Step 4: 提交** — `git commit -am "ci: GitHub Actions + GitLab unit-test job"`

### Task 19: 打包验证

**Files:**
- Modify: `pyproject.toml`（如构建报错）

- [ ] **Step 1: 构建** — `python -m build` → 产出 `dist/coding_agent_harness-0.1.0-*.whl`

- [ ] **Step 2: 干净环境安装** — 新 venv 中 `pip install dist/*.whl` → `cah --help` 可运行

- [ ] **Step 3: 提交** — 无代码改动则跳过提交；有改动则 `git commit -am "build: fix packaging"`

### Task 20: 部署配置

**Files:**
- Create: `render.yaml`

- [ ] **Step 1: 编写 render.yaml** — web service：build `pip install -e ".[dev]"`，start `uvicorn cah.web.app:app --host 0.0.0.0 --port $PORT`，env `HARNESS_DEMO=1`（强制 demo 模式）。

- [ ] **Step 2: web/app.py 支持 `HARNESS_DEMO`** — `create_app()` 读取环境变量，demo 模式下拒绝非演示接口（或强制 mock + 只读）。

- [ ] **Step 3: 提交** — `git commit -am "deploy: render blueprint with demo mode"`

---

## 冷启动验证（§4.5）指定任务

冷启动 agent（Claude Code，全新 session）从本计划中选择 **Task 5（命令护栏）与 Task 8（HITL 状态机）** 各实现一遍（含 TDD 红绿步骤），遇不确定即暂停提问。结果记录进 `SPEC_PROCESS.md` §六。
