#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/translate_vin02a2_att_trans_batches.py"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_vin02a2_att_translation.sh --items <N> [--start-line <LINE>] [--batch-size 5] [--sleep-seconds 2] [--model gpt-5.3-codex] [--dry-run]

Examples:
  ./scripts/run_vin02a2_att_translation.sh --items 10
  ./scripts/run_vin02a2_att_translation.sh --items 20 --start-line 2501
  ./scripts/run_vin02a2_att_translation.sh --items 10 --dry-run
EOF
}

ITEMS=""
START_LINE="1"
BATCH_SIZE="5"
SLEEP_SECONDS="2"
MODEL="gpt-5.3-codex"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --items)
      ITEMS="${2:-}"
      shift 2
      ;;
    --start-line)
      START_LINE="${2:-}"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --sleep-seconds)
      SLEEP_SECONDS="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${ITEMS}" ]]; then
  echo "ERROR: --items is required" >&2
  usage
  exit 1
fi

if ! [[ "${ITEMS}" =~ ^[0-9]+$ ]] || [[ "${ITEMS}" -le 0 ]]; then
  echo "ERROR: --items must be a positive integer" >&2
  exit 1
fi

if ! [[ "${START_LINE}" =~ ^[0-9]+$ ]] || [[ "${START_LINE}" -le 0 ]]; then
  echo "ERROR: --start-line must be a positive integer" >&2
  exit 1
fi

if ! [[ "${BATCH_SIZE}" =~ ^[0-9]+$ ]] || [[ "${BATCH_SIZE}" -le 0 ]]; then
  echo "ERROR: --batch-size must be a positive integer" >&2
  exit 1
fi

if ! [[ "${SLEEP_SECONDS}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "ERROR: --sleep-seconds must be a non-negative number" >&2
  exit 1
fi

CODEX_BIN="$(command -v codex || true)"
if [[ -z "${CODEX_BIN}" && -x "/Users/jb.park/.vscode/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex" ]]; then
  CODEX_BIN="/Users/jb.park/.vscode/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex"
fi

if [[ -z "${CODEX_BIN}" ]]; then
  echo "ERROR: codex 실행 파일을 찾지 못했습니다." >&2
  echo "확인 경로: PATH, /Users/jb.park/.vscode/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex" >&2
  exit 1
fi

echo "Root      : ${ROOT_DIR}"
echo "Script    : ${PY_SCRIPT}"
echo "Model     : ${MODEL}"
echo "Items     : ${ITEMS}"
echo "BatchSize : ${BATCH_SIZE}"
echo "SleepSec  : ${SLEEP_SECONDS}"
echo "StartLine : ${START_LINE}"
echo "CodexBin  : ${CODEX_BIN}"
if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Mode      : DRY RUN"
fi
echo

CMD=(
  python3 "${PY_SCRIPT}"
  --items "${ITEMS}"
  --batch-size "${BATCH_SIZE}"
  --start-line "${START_LINE}"
  --model "${MODEL}"
  --codex-bin "${CODEX_BIN}"
  --sleep-seconds "${SLEEP_SECONDS}"
)
if [[ "${DRY_RUN}" == "true" ]]; then
  CMD+=(--dry-run)
fi

"${CMD[@]}"
