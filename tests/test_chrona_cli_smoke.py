from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER = "cli_smoke"


def run_cli(*args: str) -> dict:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    completed = subprocess.run(
        [sys.executable, "-m", "chrona_cli", "--root", str(ROOT), "--user", USER, "--offline", *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(completed.stdout)


def reset_user() -> None:
    path = ROOT / "data" / "users" / USER
    if path.exists():
        shutil.rmtree(path)


def test_chrona_cli_status_add_schedule_recover_smoke() -> None:
    reset_user()
    try:
        status = run_cli("status")
        assert status["pending_count"] == 0

        added = run_cli("task", "add", "明天晚上前写实验报告，大概40分钟，要安静")
        task_id = added["added_task_ids"][0]
        assert task_id

        scheduled = run_cli("schedule")
        assert scheduled["result"]["blocks"]

        recovered = run_cli("recover", "--missed", task_id)
        assert recovered["missed_task_id"] == task_id
        assert task_id in recovered["affected_task_ids"]
    finally:
        reset_user()


if __name__ == "__main__":
    test_chrona_cli_status_add_schedule_recover_smoke()
    print("chrona cli smoke passed")
