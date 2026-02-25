#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [ ! -d "$VENV_DIR" ]; then
  echo "Virtual env not found at $VENV_DIR"
  echo "Run: bash scripts/termux-setup.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

export SERVER_WORKERS="${SERVER_WORKERS:-1}"
export LOG_FILE_ENABLED="${LOG_FILE_ENABLED:-false}"
export DATA_DIR="${DATA_DIR:-$ROOT_DIR/data}"

cd "$ROOT_DIR"
exec python main.py
