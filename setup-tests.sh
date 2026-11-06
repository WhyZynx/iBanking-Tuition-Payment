#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-run}"

# Project-local paths
TOOLS_DIR="$ROOT_DIR/.tools"
UV_BIN="$TOOLS_DIR/uv"
VENV_DIR="$ROOT_DIR/.venv-ibanking-tests"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$ROOT_DIR/requirements-test.txt"

# Keep uv, Python and its cache inside the project
export UV_PYTHON_INSTALL_DIR="$TOOLS_DIR/python"
export UV_CACHE_DIR="$ROOT_DIR/.cache/uv"

prepare_environment() {
    # Check required files and commands
    if [[ ! -f "$REQUIREMENTS" ]]; then
        echo "Error: requirements-test.txt not found." >&2
        exit 1
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: curl is required." >&2
        exit 1
    fi

    mkdir -p "$TOOLS_DIR"

    # Install uv locally if it does not exist
    if [[ ! -x "$UV_BIN" ]]; then
        echo "Installing uv locally..."

        curl -LsSf https://astral.sh/uv/install.sh \
            | env UV_INSTALL_DIR="$TOOLS_DIR" sh
    fi

    if [[ ! -x "$UV_BIN" ]]; then
        echo "Error: uv installation failed." >&2
        exit 1
    fi

    # Install Python 3.13 locally
    echo "Installing Python 3.13..."
    "$UV_BIN" python install 3.13

    # Recreate venv if it does not use Python 3.13
    if [[ -x "$VENV_PYTHON" ]]; then
        version="$("$VENV_PYTHON" -c \
            'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

        if [[ "$version" != "3.13" ]]; then
            echo "Existing venv uses Python $version. Recreating..."
            rm -rf "$VENV_DIR"
        fi
    fi

    # Create virtual environment
    if [[ ! -x "$VENV_PYTHON" ]]; then
        echo "Creating virtual environment..."
        "$UV_BIN" venv --python 3.13 "$VENV_DIR"
    fi

    # Install test dependencies
    echo "Installing test dependencies..."
    "$UV_BIN" pip install \
        --python "$VENV_PYTHON" \
        -r "$REQUIREMENTS"

    echo
    echo "Test environment is ready!"
    "$VENV_PYTHON" --version
}

run_tests() {
    if [[ ! -x "$VENV_PYTHON" ]]; then
        echo "Test environment not found."
        echo "Run ./setup-tests.sh prepare first."
        exit 1
    fi

    "$VENV_PYTHON" -m pytest -q
}

case "$MODE" in
    prepare)
        prepare_environment
        ;;
    run)
        run_tests
        ;;
    *)
        echo "Usage: ./setup-tests.sh [prepare|run]" >&2
        exit 2
        ;;
esac