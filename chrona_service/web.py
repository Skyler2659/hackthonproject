from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from chrona_service.config import ChronaConfig
from chrona_service.exceptions import ChronaServiceError


DEFAULT_PORT = 8501


def web_url(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def web_status(config: ChronaConfig, *, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    return {
        "url": web_url(port),
        "port": port,
        "running": port_is_open("127.0.0.1", port),
        "root": str(config.root),
        "app": str(config.root / "app.py"),
    }


def start_web(config: ChronaConfig, *, port: int = DEFAULT_PORT, wait_sec: float = 8.0) -> Dict[str, Any]:
    status = web_status(config, port=port)
    if status["running"]:
        return {**status, "started": False, "message": "Streamlit is already reachable."}
    app_path = config.root / "app.py"
    if not app_path.exists():
        raise ChronaServiceError(f"Streamlit app not found: {app_path}")
    python = resolve_python(config.root)
    out_log = config.root / "streamlit.out.log"
    err_log = config.root / "streamlit.err.log"
    cmd = [
        python,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with out_log.open("ab") as stdout, err_log.open("ab") as stderr:
        subprocess.Popen(
            cmd,
            cwd=str(config.root),
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if port_is_open("127.0.0.1", port):
            return {**web_status(config, port=port), "started": True, "message": "Streamlit started."}
        time.sleep(0.25)
    return {
        **web_status(config, port=port),
        "started": True,
        "message": "Streamlit launch command was issued; server is still warming up or failed. Check streamlit.err.log.",
    }


def resolve_python(root: Path) -> str:
    candidates: List[str] = []
    for env_name in ("CHRONA_PYTHON", "PYTHON"):
        raw = os.environ.get(env_name)
        if raw:
            candidates.append(raw)
    candidates.extend(
        [
            str(root / ".venv" / "Scripts" / "python.exe"),
            str(root / ".venv" / "bin" / "python"),
            sys.executable,
            "python",
            "python3",
        ]
    )
    for candidate in candidates:
        if (candidate in {"python", "python3"} or Path(candidate).exists()) and python_works(candidate):
            return candidate
    raise ChronaServiceError("No Python executable found. Set CHRONA_PYTHON to a Python with Streamlit installed.")


def python_works(candidate: str) -> bool:
    try:
        completed = subprocess.run(
            [candidate, "-c", "import sys"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False
