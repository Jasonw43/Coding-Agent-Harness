"""Shared pytest fixtures for the cah test suite."""
"""Shared fixtures for the harness test suite."""

import pytest

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def registry(workspace):
    return ToolRegistry(sandbox=WorkspaceSandbox(workspace, read_only=False))
