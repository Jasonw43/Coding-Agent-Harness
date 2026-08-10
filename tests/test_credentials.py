"""Deterministic tests for the credentials manager (keyring mocked)."""

import pytest

from cah.credentials.manager import CredentialsManager


class _FakeKeyring:
    def __init__(self, store):
        self.store = store

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


@pytest.fixture
def mgr(monkeypatch, tmp_path):
    store = {}
    monkeypatch.setattr("cah.credentials.manager.keyring", _FakeKeyring(store))
    return CredentialsManager(service="test", env_prefix="TEST", env_file=tmp_path / ".env")


def test_set_status_clear(mgr):
    mgr.set_key("sk-123456")
    st = mgr.status()
    assert st["configured"] and "sk-123456" not in st["masked"]
    assert mgr.get_key() == "sk-123456"
    mgr.clear()
    assert not mgr.status()["configured"]


def test_env_file_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("cah.credentials.manager.keyring", _FakeKeyring({}))
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_API_KEY=env-file-key\n", encoding="utf-8")
    mgr = CredentialsManager(service="t", env_prefix="TEST", env_file=env_file)
    assert mgr.get_key() == "env-file-key"
    assert mgr.status()["source"] == "env_file"


def test_env_var_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("cah.credentials.manager.keyring", _FakeKeyring({}))
    monkeypatch.setenv("TEST_API_KEY", "env-var-key")
    mgr = CredentialsManager(service="t", env_prefix="TEST", env_file=tmp_path / ".env")
    assert mgr.get_key() == "env-var-key"
    assert mgr.status()["source"] == "env"
