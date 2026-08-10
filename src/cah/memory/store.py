"""Persistent key-value memory store with keyword/tag recall."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class MemoryEntry:
    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class MemoryStore:
    """JSON-file-backed store; recall returns only matching snippets."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else []
            self._entries = {e["key"]: e for e in items if isinstance(e, dict) and "key" in e}
        except (json.JSONDecodeError, OSError):
            # corrupted store: back it up and rebuild
            try:
                os.replace(self.path, self.path.with_suffix(".json.bak"))
            except OSError:
                pass
            self._entries = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".memory-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(list(self._entries.values()), f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def store(self, key: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
        entry = MemoryEntry(key=key, content=content, tags=list(tags or []))
        self._entries[key] = asdict(entry)
        self._save()
        return entry

    def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        q = query.lower()
        hits: list[MemoryEntry] = []
        for raw in self._entries.values():
            entry = MemoryEntry(**raw)
            haystack = " ".join([entry.key, entry.content, " ".join(entry.tags)]).lower()
            if q in haystack:
                hits.append(entry)
            if len(hits) >= limit:
                break
        return hits

    def all_entries(self) -> list[MemoryEntry]:
        return [MemoryEntry(**raw) for raw in self._entries.values()]
