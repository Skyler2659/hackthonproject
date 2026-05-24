from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_USER = "admin"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"


@dataclass(frozen=True)
class ChronaConfig:
    root: Path
    user: str
    api_key: str
    base_url: str
    model: str
    offline: bool = False


def resolve_config(
    *,
    root: str | None = None,
    user: str | None = None,
    offline: bool | None = None,
) -> ChronaConfig:
    project_root = resolve_root(root)
    load_dotenv(project_root / ".env")
    return ChronaConfig(
        root=project_root,
        user=normalize_user(user or os.environ.get("CHRONA_USER") or DEFAULT_USER),
        api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        base_url=(
            os.environ.get("DEEPSEEK_BASE_URL")
            or os.environ.get("CHRONA_LLM_BASE_URL")
            or DEFAULT_BASE_URL
        ).strip(),
        model=(
            os.environ.get("CHRONA_LLM_MODEL")
            or os.environ.get("DEEPSEEK_MODEL")
            or DEFAULT_MODEL
        ).strip(),
        offline=bool_from_env("CHRONA_OFFLINE") if offline is None else bool(offline),
    )


def resolve_root(root: str | None = None) -> Path:
    raw = root or os.environ.get("CHRONA_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return find_project_root(Path.cwd())


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "app.py").exists() and (candidate / "web_ui").is_dir():
            return candidate
    return current


def normalize_user(user: str) -> str:
    return str(user or DEFAULT_USER).strip().lower() or DEFAULT_USER


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        parsed = parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")


def bool_from_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
