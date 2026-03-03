#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/translate_s0101m_trans_batches_claude.py"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_s0101m_translation_claude.sh --items <N> [--start-line <LINE>] [--batch-size 5] [--sleep-seconds 2] [--model claude-sonnet-4-6] [--dry-run]

Examples:
  ./scripts/run_s0101m_translation_claude.sh --items 10
  ./scripts/run_s0101m_translation_claude.sh --items 20 --start-line 2501
  ./scripts/run_s0101m_translation_claude.sh --items 10 --dry-run
EOF
}

ITEMS=""
START_LINE="1"
BATCH_SIZE="5"
SLEEP_SECONDS="2"
MODEL="claude-sonnet-4-6"
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

CLAUDE_BIN="$(command -v claude || true)"

if [[ -z "${CLAUDE_BIN}" ]]; then
  echo "ERROR: claude 실행 파일을 찾지 못했습니다." >&2
  echo "확인: PATH에 claude CLI가 설치되어 있는지 확인하세요." >&2
  echo "설치: npm install -g @anthropic-ai/claude-code" >&2
  exit 1
fi

echo "Root      : ${ROOT_DIR}"
echo "Script    : ${PY_SCRIPT}"
echo "Model     : ${MODEL}"
echo "Items     : ${ITEMS}"
echo "BatchSize : ${BATCH_SIZE}"
echo "SleepSec  : ${SLEEP_SECONDS}"
echo "StartLine : ${START_LINE}"
echo "ClaudeBin : ${CLAUDE_BIN}"
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
  --claude-bin "${CLAUDE_BIN}"
  --sleep-seconds "${SLEEP_SECONDS}"
)
if [[ "${DRY_RUN}" == "true" ]]; then
  CMD+=(--dry-run)
fi

"${CMD[@]}"
