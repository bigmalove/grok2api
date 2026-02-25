#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if ! command -v pkg >/dev/null 2>&1; then
  echo "This script is intended for Termux."
  exit 1
fi

pkg update -y
pkg install -y python git clang rust make pkg-config libffi openssl

python -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# pydantic-core (via maturin/pyo3) needs Android API level in Termux.
ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-$(getprop ro.build.version.sdk 2>/dev/null || true)}"
if [ -z "$ANDROID_API_LEVEL" ]; then
  ANDROID_API_LEVEL=24
fi
export ANDROID_API_LEVEL

echo "Using ANDROID_API_LEVEL=$ANDROID_API_LEVEL"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$ROOT_DIR/requirements.txt"

if [ ! -f "$ROOT_DIR/.env" ]; then
  cat > "$ROOT_DIR/.env" <<'EOF'
LOG_LEVEL=INFO
LOG_FILE_ENABLED=false
DATA_DIR=./data
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
EOF
fi

echo "Termux setup complete."
echo "Run: bash scripts/termux-run.sh"
