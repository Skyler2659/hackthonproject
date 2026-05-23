from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional, Protocol

from core.exceptions import ReplayConflictError


class LLMClient(Protocol):
    def generate_json(
        self,
        system_prompt: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...


class ReplayGuard:
    def __init__(self) -> None:
        self._key_fingerprints: Dict[str, str] = {}

    def guard(
        self,
        system_prompt: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str],
    ) -> str:
        fingerprint = fingerprint_request(system_prompt, payload)
        if not idempotency_key:
            return fingerprint

        previous = self._key_fingerprints.get(idempotency_key)
        if previous and previous != fingerprint:
            raise ReplayConflictError(
                f"idempotency key reused with different payload: {idempotency_key}"
            )
        self._key_fingerprints[idempotency_key] = fingerprint
        return fingerprint


def fingerprint_request(system_prompt: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps(
        {"system_prompt": system_prompt, "payload": payload},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            key_value = parse_env_line(raw_line)
            if key_value is None:
                continue
            key, value = key_value
            os.environ.setdefault(key, value)


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, value = line.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")
