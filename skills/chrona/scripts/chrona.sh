#!/usr/bin/env bash
set -euo pipefail

resolve_root() {
  if [[ -n "${CHRONA_ROOT:-}" ]]; then
    cd "$CHRONA_ROOT"
    pwd
    return
  fi
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local candidate
  candidate="$(cd "$script_dir/../../.." && pwd)"
  if [[ -f "$candidate/app.py" ]]; then
    echo "$candidate"
    return
  fi
  echo "Set CHRONA_ROOT to the Chrona project root containing app.py." >&2
  exit 2
}

resolve_python() {
  local root="$1"
  if [[ -n "${CHRONA_PYTHON:-}" ]]; then
    echo "$CHRONA_PYTHON"
    return
  fi
  if [[ -x "$root/.venv/bin/python" ]] && "$root/.venv/bin/python" -c 'import sys' >/dev/null 2>&1; then
    echo "$root/.venv/bin/python"
    return
  fi
  if [[ -x "$root/.venv/Scripts/python.exe" ]] && "$root/.venv/Scripts/python.exe" -c 'import sys' >/dev/null 2>&1; then
    echo "$root/.venv/Scripts/python.exe"
    return
  fi
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  if command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
    echo "python"
    return
  fi
  echo "No Python executable found. Set CHRONA_PYTHON." >&2
  exit 2
}

ROOT="$(resolve_root)"
PYTHON="$(resolve_python "$ROOT")"
cd "$ROOT"
exec "$PYTHON" -m chrona_cli "$@"
