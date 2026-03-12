#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
import tempfile
import shutil
import time
from pathlib import Path
from typing import List, Tuple
import xml.etree.ElementTree as ET


SYSTEM_PROMPT = (
    "당신은 Pali 불전 한국어 번역가다. "
    "목표: XML 태그는 그대로 두고, 태그 내부 텍스트를 한국어로 완전 직역한다."
    "수작업 직역 원칙으로 번역하며 요약/의역/삭제를 금지한다."
)

ROOT_DIR = Path(__file__).resolve().parent.parent
TARGET_XML = ROOT_DIR / "data/corpus/ko/vin02a3.att.xml"


def is_translatable(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return re.search(r"[A-Za-zĀĪŪṂṀÑṆḌḶḤṭḍṅñṇṃṁāīū]", t) is not None


def resolve_codex_bin(user_bin: str = "") -> str:
    candidates = []
    if user_bin:
        candidates.append(user_bin)
    found = shutil.which("codex")
    if found:
        candidates.append(found)
    candidates.extend(
        [
            "/Users/jb.park/.vscode/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex",
            "/opt/homebrew/bin/codex",
            "/usr/local/bin/codex",
        ]
    )
    for c in candidates:
        p = Path(c).expanduser()
        if p.is_file():
            return str(p)
    raise FileNotFoundError(
        "codex 실행 파일을 찾지 못했습니다. "
        "--codex-bin으로 경로를 지정하세요. "
        "예: --codex-bin /Users/jb.park/.vscode/extensions/openai.chatgpt-0.4.79-darwin-arm64/bin/macos-aarch64/codex"
    )


def _run_codex_list_once(texts: List[str], model: str, codex_bin: str) -> List[str]:
    schema = {
        "type": "object",
        "properties": {
            "translations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["translations"],
        "additionalProperties": False,
    }

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "아래 JSON 배열의 각 원소를 같은 순서로 한국어로 번역하라.\n"
        "- 원문 구조/정보량 유지\n"
        "- '...pe...' 표기는 그대로 유지\n"
        "- 원문 약호/고유어는 가능하면 병기\n"
        "- 설명문/코드블록 없이 JSON만 출력\n\n"
        f"{json.dumps(texts, ensure_ascii=False)}"
    )

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        schema_path = tdp / "schema.json"
        out_path = tdp / "out.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        cmd = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(out_path),
            "-m",
            model,
            "-",
        ]
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exec failed (exit={proc.returncode})\n"
                f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
            )
        if not out_path.exists():
            raise RuntimeError("codex output file missing")
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        arr = parsed.get("translations")
        if not isinstance(arr, list) or len(arr) != len(texts):
            raise RuntimeError(
                f"translation length mismatch: expected={len(texts)} got={len(arr) if isinstance(arr, list) else 'invalid'}"
            )
        return [str(x).strip() for x in arr]


def _run_codex_single_once(text: str, model: str, codex_bin: str) -> str:
    schema = {
        "type": "object",
        "properties": {"translation": {"type": "string"}},
        "required": ["translation"],
        "additionalProperties": False,
    }
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "아래 텍스트 1개를 한국어로 번역하라.\n"
        "- 원문 구조/정보량 유지\n"
        "- '...pe...' 표기는 그대로 유지\n"
        "- 설명문/코드블록 없이 JSON만 출력\n\n"
        f"{json.dumps(text, ensure_ascii=False)}"
    )
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        schema_path = tdp / "schema.json"
        out_path = tdp / "out.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        cmd = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(out_path),
            "-m",
            model,
            "-",
        ]
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exec failed (single, exit={proc.returncode})\n"
                f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
            )
        if not out_path.exists():
            raise RuntimeError("codex output file missing (single)")
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
        val = parsed.get("translation")
        if not isinstance(val, str):
            raise RuntimeError("invalid single translation output")
        return val.strip()


def run_codex_translate_batch(
    texts: List[str], model: str, codex_bin: str, depth: int = 0, max_depth: int = 6
) -> List[str]:
    if not texts:
        return []

    # First, retry the current batch a few times as-is.
    last_err: Exception = RuntimeError("unknown")
    for attempt in range(1, 4):
        try:
            return _run_codex_list_once(texts, model, codex_bin)
        except Exception as e:
            last_err = e
            print(
                f"  ! batch translate failed (attempt {attempt}/3, size={len(texts)}): {e}",
                file=sys.stderr,
            )
            time.sleep(0.5)

    # Fallback: split batch recursively.
    if len(texts) > 1 and depth < max_depth:
        mid = len(texts) // 2
        print(
            f"  ! fallback split: size={len(texts)} -> {mid}+{len(texts)-mid}",
            file=sys.stderr,
        )
        left = run_codex_translate_batch(texts[:mid], model, codex_bin, depth + 1, max_depth)
        right = run_codex_translate_batch(texts[mid:], model, codex_bin, depth + 1, max_depth)
        return left + right

    # Last fallback: single strict mode.
    if len(texts) == 1:
        for attempt in range(1, 4):
            try:
                return [_run_codex_single_once(texts[0], model, codex_bin)]
            except Exception as e:
                last_err = e
                print(
                    f"  ! single fallback failed (attempt {attempt}/3): {e}",
                    file=sys.stderr,
                )
                time.sleep(0.5)

    raise RuntimeError(f"batch translation unrecoverable: size={len(texts)} err={last_err}")


def collect_text_slots(elem: ET.Element) -> List[Tuple[ET.Element, str]]:
    slots: List[Tuple[ET.Element, str]] = []

    def walk(node: ET.Element):
        if is_translatable(node.text):
            slots.append((node, "text"))
        for child in list(node):
            walk(child)
            if is_translatable(child.tail):
                slots.append((child, "tail"))

    walk(elem)
    return slots


def set_trans_true(node: ET.Element):
    # Root target tag should always become trans=true after translation.
    if node.attrib.get("trans") != "true":
        node.attrib["trans"] = "true"
    # Child tags: only flip existing trans=false recursively.
    def _recurse(n: ET.Element):
        for ch in list(n):
            if ch.attrib.get("trans") == "false":
                ch.attrib["trans"] = "true"
            _recurse(ch)
    _recurse(node)


def is_trans_false_target_line(raw: str) -> bool:
    s = raw.strip()
    if not s.startswith("<") or s.startswith("</") or s.startswith("<?") or s.startswith("<!"):
        return False
    m = re.match(r"^<([A-Za-z_][A-Za-z0-9_.:-]*)\b", s)
    if not m:
        return False
    tag = m.group(1)
    if 'trans="false"' in s:
        return True
    # Some files may miss trans on heading tags; include them for recovery.
    if "trans=" not in s and tag in {"head", "trailer", "p", "note"}:
        return True
    return False


def find_target_lines(lines: List[str], start_line: int, limit: int) -> List[int]:
    targets = []
    for i, raw in enumerate(lines, start=1):
        if i < start_line:
            continue
        if is_trans_false_target_line(raw):
            targets.append(i)
            if len(targets) >= limit:
                break
    return targets


def main():
    ap = argparse.ArgumentParser(
        description="vin02a3.att.xml trans=false 단락을 배치 번역하고 trans=true로 반영"
    )
    ap.add_argument("--items", type=int, required=True, help="처리할 단락 수 (예: 10, 20)")
    ap.add_argument("--batch-size", type=int, default=5, help="배치 크기 (기본 5)")
    ap.add_argument("--start-line", type=int, default=1, help="검색 시작 라인 (기본 1)")
    ap.add_argument("--model", default="gpt-5.3-codex", help="codex model")
    ap.add_argument("--codex-bin", default="", help="codex 실행 파일 경로 (선택)")
    ap.add_argument("--sleep-seconds", type=float, default=2.0, help="배치 간 대기 시간(초), 기본 2.0")
    ap.add_argument("--dry-run", action="store_true", help="실제 수정 없이 대상만 출력")
    args = ap.parse_args()

    if args.items <= 0:
        raise SystemExit("--items must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")

    codex_bin = resolve_codex_bin(args.codex_bin)

    lines = TARGET_XML.read_text(encoding="utf-8").splitlines(keepends=True)
    all_false = [i for i, raw in enumerate(lines, start=1) if is_trans_false_target_line(raw)]
    targets = find_target_lines(lines, args.start_line, args.items)
    if not targets:
        print("대상 단락이 없습니다.")
        return

    print(f"파일: {TARGET_XML}")
    print(f"전체 미번역 태그(trans=false): {len(all_false)}")
    print(f"요청 단락 수: {args.items}, 실제 처리 수: {len(targets)}")
    print(f"시작 라인: {targets[0]}, 종료 라인: {targets[-1]}")
    if args.items % args.batch_size != 0:
        print(
            f"경고: items({args.items})가 batch-size({args.batch_size})로 나누어떨어지지 않습니다.",
            file=sys.stderr,
        )
    if args.dry_run:
        print("DRY RUN 대상 라인:", ", ".join(str(x) for x in targets))
        return

    batches = [targets[i : i + args.batch_size] for i in range(0, len(targets), args.batch_size)]
    done = 0
    first_done = None
    last_done = None

    for bidx, batch_lines in enumerate(batches, start=1):
        elems: List[ET.Element] = []
        slots_by_elem: List[List[Tuple[ET.Element, str]]] = []
        texts: List[str] = []
        counts: List[int] = []

        for ln in batch_lines:
            raw = lines[ln - 1].strip()
            try:
                elem = ET.fromstring(raw)
            except ET.ParseError as e:
                raise RuntimeError(f"line {ln} XML parse error: {e}") from e
            slots = collect_text_slots(elem)
            for node, kind in slots:
                texts.append(node.text if kind == "text" else node.tail)
            elems.append(elem)
            slots_by_elem.append(slots)
            counts.append(len(slots))

        print(
            f"[batch {bidx}/{len(batches)}] "
            f"lines {batch_lines[0]}-{batch_lines[-1]} | paragraphs={len(batch_lines)} | text_slots={sum(counts)}"
        )
        outs = run_codex_translate_batch(texts, args.model, codex_bin)

        cursor = 0
        for i, ln in enumerate(batch_lines):
            slots = slots_by_elem[i]
            seg_n = counts[i]
            segs = outs[cursor : cursor + seg_n]
            cursor += seg_n
            for (node, kind), val in zip(slots, segs):
                if kind == "text":
                    node.text = val
                else:
                    node.tail = val
            set_trans_true(elems[i])
            rendered = ET.tostring(elems[i], encoding="unicode", short_empty_elements=True)
            lines[ln - 1] = rendered + "\n"
            done += 1
            if first_done is None:
                first_done = ln
            last_done = ln

        pct = done / len(targets) * 100.0
        print(f"  -> batch done: {done}/{len(targets)} ({pct:.1f}%)")
        # Persist each completed batch immediately.
        TARGET_XML.write_text("".join(lines), encoding="utf-8")
        print("  -> saved to file")
        if bidx < len(batches) and args.sleep_seconds > 0:
            print(f"  -> sleep {args.sleep_seconds:.1f}s before next batch")
            time.sleep(args.sleep_seconds)

    after_lines = TARGET_XML.read_text(encoding="utf-8").splitlines()
    remain_false = sum(1 for raw in after_lines if is_trans_false_target_line(raw))
    print("")
    print("[완료 요약]")
    print(f"- 시작 라인: {first_done}")
    print(f"- 종료 라인: {last_done}")
    print(f"- 처리 단락 수: {done}")
    print(f"- 남은 미번역 태그(trans=false): {remain_false}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
