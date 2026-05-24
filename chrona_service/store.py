from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from chrona_service.config import normalize_user
from chrona_service.profile import DEFAULT_MEMORY


def user_data_dir(root: Path, user: str) -> Path:
    return root / "data" / "users" / normalize_user(user)


def archive_path(root: Path, user: str) -> Path:
    return user_data_dir(root, user) / "session_archive.json"


def profile_memory_path(root: Path, user: str) -> Path:
    return user_data_dir(root, user) / "user_profile_memory.json"


def empty_archive() -> Dict[str, Any]:
    return {
        "pending_tasks": [],
        "operation_history": [],
        "last_scores": None,
        "last_result": None,
        "last_profile": None,
        "last_run_at": None,
    }


def load_archive(root: Path, user: str) -> Dict[str, Any]:
    payload = read_json(archive_path(root, user), default={})
    archive = empty_archive()
    if isinstance(payload, dict):
        archive.update(payload)
    archive["pending_tasks"] = list(archive.get("pending_tasks") or [])
    archive["operation_history"] = list(archive.get("operation_history") or [])
    return archive


def save_archive(root: Path, user: str, archive: Dict[str, Any]) -> None:
    path = archive_path(root, user)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = empty_archive()
    payload.update(archive)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile_memory(root: Path, user: str) -> Dict[str, Any]:
    payload = read_json(profile_memory_path(root, user), default={})
    memory = deepcopy(DEFAULT_MEMORY)
    if isinstance(payload, dict):
        memory.update({key: value for key, value in payload.items() if key in memory})
        memory["weights"] = {**DEFAULT_MEMORY["weights"], **dict(payload.get("weights", {}))}
        memory["answers"] = dict(payload.get("answers", {}))
    return memory


def save_profile_memory(root: Path, user: str, memory: Dict[str, Any]) -> None:
    path = profile_memory_path(root, user)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def append_operation(
    archive: Dict[str, Any],
    operation: str,
    *,
    task_id: str = "",
    title: str = "",
    detail: str = "",
) -> None:
    archive.setdefault("operation_history", [])
    archive["operation_history"].append(
        {
            "operation": operation,
            "task_id": task_id,
            "title": title,
            "detail": detail,
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
        }
    )
