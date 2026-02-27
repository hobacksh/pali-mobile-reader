#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/translate_local_corpus_with_codex.sh --file <romn-file.xml> [--model gpt-5] [--batch-size 80] [--max-chars 2000]

Example:
  ./scripts/translate_local_corpus_with_codex.sh --file vin01m.mul.xml --model gpt-5
EOF
}

FILE=""
MODEL="gpt-5"
BATCH_SIZE="80"
MAX_CHARS="2000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      FILE="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="${2:-}"
      shift 2
      ;;
    --max-chars)
      MAX_CHARS="${2:-}"
      shift 2
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

if [[ -z "${FILE}" ]]; then
  echo "ERROR: --file is required" >&2
  usage
  exit 1
fi

IN_PATH="${ROOT_DIR}/data/corpus/romn/${FILE}"
OUT_PATH="${ROOT_DIR}/data/corpus/ko/${FILE}"

if [[ ! -f "${IN_PATH}" ]]; then
  echo "ERROR: input not found: ${IN_PATH}" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT_PATH}")"

echo "Input : ${IN_PATH}"
echo "Output: ${OUT_PATH}"

python3 "${SCRIPT_DIR}/translate_one_xml_with_codex.py" \
  --input "${IN_PATH}" \
  --output "${OUT_PATH}" \
  --model "${MODEL}" \
  --batch-size "${BATCH_SIZE}" \
  --max-chars "${MAX_CHARS}"

echo "Done."
