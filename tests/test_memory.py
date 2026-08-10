"""Deterministic tests for the persistent memory store."""

from cah.memory.store import MemoryStore


def test_store_and_recall(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    ms.store("convention", "use pytest", tags=["testing"])
    hits = ms.recall("pytest")
    assert hits and hits[0].key == "convention"


def test_recall_empty(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    assert ms.recall("nothing") == []


def test_store_overwrites_same_key(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    ms.store("k", "v1", tags=["a"])
    ms.store("k", "v2", tags=["a"])
    assert len(ms.recall("v2")) == 1 and ms.recall("v2")[0].content == "v2"


def test_recall_by_tag(tmp_path):
    ms = MemoryStore(path=tmp_path / "memory.json")
    ms.store("rule", "never use rm -rf", tags=["safety"])
    hits = ms.recall("safety")
    assert hits and hits[0].key == "rule"


def test_persistence_across_instances(tmp_path):
    p = tmp_path / "memory.json"
    MemoryStore(path=p).store("x", "hello", tags=[])
    ms2 = MemoryStore(path=p)
    assert ms2.recall("hello")[0].content == "hello"
