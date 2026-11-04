#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
MODE="${1:-run}"
VENV_DIR="$ROOT_DIR/.venv-ibanking-tests"
VENV_PYTHON="$VENV_DIR/bin/python"

find_python() {
  local candidate version
  for candidate in python3.12 python3.13 python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version="$("$candidate" -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))')"
    if [[ "$version" == 3.12 || "$version" == 3.13 ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ "$MODE" == prepare ]]; then
  python_command="$(find_python)" || {
    printf 'Python 3.12 or 3.13 is required. Install it and retry; no global packages were changed.\n' >&2
    exit 1
  }
  if [[ ! -x "$VENV_PYTHON" ]]; then
    if [[ -e "$VENV_DIR" ]]; then
      printf '.venv-ibanking-tests exists but is incomplete; inspect it before retrying.\n' >&2
      exit 1
    fi
    "$python_command" -m venv "$VENV_DIR"
  fi
  version="$("$VENV_PYTHON" -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))')"
  [[ "$version" == 3.12 || "$version" == 3.13 ]] || {
    printf '.venv-ibanking-tests must use Python 3.12 or 3.13; it was not replaced.\n' >&2
    exit 1
  }
  "$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$ROOT_DIR/requirements-test.txt"
  printf 'Prepared isolated pytest environment: %s\n' "$version"
elif [[ "$MODE" == run ]]; then
  [[ -x "$VENV_PYTHON" ]] || {
    printf 'Run ./setup-tests.sh prepare first or use setup.sh.\n' >&2
    exit 1
  }
  "$VENV_PYTHON" -m pytest -q
else
  printf 'Usage: ./setup-tests.sh [prepare|run]\n' >&2
  exit 2
fi
