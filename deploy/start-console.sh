#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export GROK_REGISTER_SOURCE_DIR="${GROK_REGISTER_SOURCE_DIR:-$ROOT_DIR}"
export GROK_REGISTER_PYTHON="${GROK_REGISTER_PYTHON:-$ROOT_DIR/.venv/bin/python}"
export GROK_REGISTER_CONSOLE_MAX_CONCURRENT_TASKS="${GROK_REGISTER_CONSOLE_MAX_CONCURRENT_TASKS:-1}"
export SERVER_HOST="${SERVER_HOST:-0.0.0.0}"
export SERVER_PORT="${SERVER_PORT:-8000}"
export SERVER_WORKERS="${SERVER_WORKERS:-1}"

cd "$ROOT_DIR"
exec "$GROK_REGISTER_PYTHON" -m granian --interface asgi --host "$SERVER_HOST" --port "$SERVER_PORT" --workers "$SERVER_WORKERS" app.main:app
