"""Secure credential storage: OS keyring first, env/.env as fallback.

Plaintext keys are never printed, logged, or committed. The `.env` fallback is
plaintext on disk and its risk is documented in the README.
"""

from __future__ import annotations

import os
from pathlib import Path

import keyring


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****"


class CredentialsManager:
    """Store/retrieve an API key with keyring as primary source."""

    def __init__(
        self,
        service: str = "cah",
        env_prefix: str = "CAH",
        env_file: str | Path = ".env",
    ) -> None:
        self.service = service
        self.username = "default"
        self.env_var = f"{env_prefix}_API_KEY"
        self.env_file = Path(env_file)

    # ---- write ----

    def set_key(self, value: str) -> str:
        """Store the key; returns the storage source used."""
        try:
            keyring.set_password(self.service, self.username, value)
            return "keyring"
        except Exception:
            self._write_env_file(value)
            return "env_file (plaintext fallback)"

    # ---- read ----

    def get_key(self) -> str | None:
        source = self.status().get("source")
        if source == "keyring":
            return keyring.get_password(self.service, self.username)
        if source == "env":
            return os.environ.get(self.env_var)
        if source == "env_file":
            return self._read_env_file()
        return None

    def status(self) -> dict:
        """Report masked status without ever echoing the plaintext key."""
        try:
            keyring_value = keyring.get_password(self.service, self.username)
        except Exception:
            keyring_value = None
        if keyring_value:
            return {"configured": True, "source": "keyring", "masked": _mask(keyring_value)}
        env_value = os.environ.get(self.env_var)
        if env_value:
            return {"configured": True, "source": "env", "masked": _mask(env_value)}
        file_value = self._read_env_file()
        if file_value:
            return {"configured": True, "source": "env_file", "masked": _mask(file_value)}
        return {"configured": False, "source": None, "masked": ""}

    # ---- delete ----

    def clear(self) -> None:
        try:
            keyring.delete_password(self.service, self.username)
        except Exception:
            pass
        self._remove_env_var()

    # ---- env file helpers ----

    def _read_env_file(self) -> str | None:
        if not self.env_file.exists():
            return None
        try:
            for line in self.env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == self.env_var:
                        return v.strip().strip('"').strip("'")
        except OSError:
            return None
        return None

    def _write_env_file(self, value: str) -> None:
        lines = []
        if self.env_file.exists():
            lines = [
                line
                for line in self.env_file.read_text(encoding="utf-8").splitlines()
                if not line.strip().startswith(f"{self.env_var}=")
            ]
        lines.append(f"{self.env_var}={value}")
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _remove_env_var(self) -> None:
        if self.env_file.exists():
            lines = [
                line
                for line in self.env_file.read_text(encoding="utf-8").splitlines()
                if not line.strip().startswith(f"{self.env_var}=")
            ]
            self.env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ.pop(self.env_var, None)
