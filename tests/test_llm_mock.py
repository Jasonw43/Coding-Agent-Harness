import json

import pytest

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
    with pytest.raises(StopIteration):
        llm.complete(context=[], available_actions=[])


def test_mock_llm_loop_wraps(tmp_path):
    p = tmp_path / "loop.jsonl"
    p.write_text('{"text":"again","action":null,"done":false}\n', encoding="utf-8")
    llm = MockLLM(script_path=p, loop=True)
    assert llm.complete(context=[], available_actions=[]).text == "again"
    assert llm.complete(context=[], available_actions=[]).text == "again"


def test_mock_llm_tolerates_bom(tmp_path):
    p = tmp_path / "bom.jsonl"
    p.write_bytes(b"\xef\xbb\xbf" + b'{"text":"ok","action":null,"done":true}\n')
    llm = MockLLM(script_path=p)
    resp = llm.complete(context=[], available_actions=[])
    assert resp.done and resp.text == "ok"
