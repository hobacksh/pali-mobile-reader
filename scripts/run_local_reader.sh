#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${PORT:-8000}"
HOST="127.0.0.1"
PID_FILE="/tmp/pali-mobile-reader-http.pid"
LOG_FILE="/tmp/pali-mobile-reader-http.log"
NO_OPEN=0
CMD="start"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_local_reader.sh [start|stop|status] [--port N] [--no-open]

Examples:
  ./scripts/run_local_reader.sh
  ./scripts/run_local_reader.sh start --port 8000
  ./scripts/run_local_reader.sh status
  ./scripts/run_local_reader.sh stop
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    start|stop|status)
      CMD="$1"
      shift
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --no-open)
      NO_OPEN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

URL="http://${HOST}:${PORT}/"

is_pid_running() {
  local pid="$1"
  kill -0 "${pid}" >/dev/null 2>&1
}

get_pid_from_file() {
  if [[ -f "${PID_FILE}" ]]; then
    cat "${PID_FILE}"
  fi
}

start_server() {
  local pid
  pid="$(get_pid_from_file || true)"
  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    echo "Server already running (pid=${pid})"
  else
    rm -f "${PID_FILE}"
    cd "${ROOT_DIR}"
    nohup python3 -m http.server "${PORT}" --bind "${HOST}" > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    pid="$(cat "${PID_FILE}")"
    echo "Starting server (pid=${pid})"
  fi

  local ok=0
  for _ in $(seq 1 30); do
    if curl -sS -o /dev/null "${URL}"; then
      ok=1
      break
    fi
    sleep 0.2
  done
  if [[ "${ok}" -ne 1 ]]; then
    echo "Server health check failed: ${URL}"
    echo "Log tail:"
    tail -n 40 "${LOG_FILE}" 2>/dev/null || true
    exit 1
  fi

  echo "Reader URL: ${URL}"
  echo "Log file: ${LOG_FILE}"

  if [[ "${NO_OPEN}" -eq 0 ]] && command -v open >/dev/null 2>&1; then
    open "${URL}" >/dev/null 2>&1 || true
  fi
}

stop_server() {
  local pid
  pid="$(get_pid_from_file || true)"
  if [[ -z "${pid}" ]]; then
    echo "No pid file. Nothing to stop."
    return
  fi
  if is_pid_running "${pid}"; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 0.3
    echo "Stopped server (pid=${pid})"
  else
    echo "Server not running (stale pid=${pid})"
  fi
  rm -f "${PID_FILE}"
}

status_server() {
  local pid
  pid="$(get_pid_from_file || true)"
  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    echo "RUNNING pid=${pid} url=${URL}"
  else
    echo "STOPPED"
  fi
}

case "${CMD}" in
  start) start_server ;;
  stop) stop_server ;;
  status) status_server ;;
esac
