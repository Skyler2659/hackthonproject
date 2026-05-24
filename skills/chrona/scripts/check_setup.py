from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path


def main() -> int:
    root = resolve_root()
    user = os.environ.get("CHRONA_USER", "admin").strip().lower() or "admin"
    checks = {
        "python": sys.executable,
        "root": str(root),
        "has_app_py": (root / "app.py").exists(),
        "has_chrona_cli": (root / "chrona_cli.py").exists(),
        "user": user,
        "user_dir_exists": (root / "data" / "users" / user).is_dir(),
        "archive_exists": (root / "data" / "users" / user / "session_archive.json").exists(),
        "profile_exists": (root / "data" / "users" / user / "user_profile_memory.json").exists(),
        "has_deepseek_key": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
        "web_url": "http://127.0.0.1:8501",
        "web_running": port_open("127.0.0.1", 8501),
    }
    checks["ok"] = bool(checks["has_app_py"] and checks["has_chrona_cli"])
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ok"] else 2


def resolve_root() -> Path:
    if os.environ.get("CHRONA_ROOT"):
        return Path(os.environ["CHRONA_ROOT"]).expanduser().resolve()
    script = Path(__file__).resolve()
    candidate = script.parents[3]
    if (candidate / "app.py").exists():
        return candidate
    return Path.cwd().resolve()


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
