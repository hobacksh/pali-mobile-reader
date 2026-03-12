#!/usr/bin/env python3
"""
translate_vin01_trans_batches_claude.py
대상 파일: data/corpus/ko/s0101m.mul.xml (Dīghanikāya DN)
codex CLI 대신 claude CLI (claude-sonnet-4-6 등)를 사용해 번역하는 버전.

claude CLI는 --output-schema / --output-last-message 옵션이 없으므로
프롬프트에서 JSON만 출력하도록 강하게 유도한 뒤 stdout을 파싱한다.
"""
import argparse
import json
import re
import subprocess
import sys
import shutil
import time
from pathlib import Path
from typing import List, Tuple
import xml.etree.ElementTree as ET


SYSTEM_PROMPT = (
    "당신은 Pali 불전 한국어 번역가다. "
    "목표: XML 태그는 그대로 두고, 태그 내부 텍스트를 한국어로 완전 직역한다. "
    "수작업 직역 원칙으로 번역하며 요약/의역/삭제를 금지한다."
)

ROOT_DIR = Path(__file__).resolve().parent.parent
TARGET_XML = ROOT_DIR / "data/corpus/ko/s0101m.mul.xml"


def is_translatable(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return re.search(r"[A-Za-zĀĪŪṂṀÑṆḌḶḤṭḍṅñṇṃṁāīū]", t) is not None


def resolve_claude_bin(user_bin: str = "") -> str:
    candidates = []
    if user_bin:
        candidates.append(user_bin)
    found = shutil.which("claude")
    if found:
        candidates.append(found)
    candidates.extend(
        [
            "/usr/local/bin/claude",
            "/opt/homebrew/bin/claude",
            str(Path.home() / ".npm-global/bin/claude"),
            str(Path.home() / ".local/bin/claude"),
        ]
    )
    for c in candidates:
        p = Path(c).expanduser()
        if p.is_file():
            return str(p)
    raise FileNotFoundError(
        "claude 실행 파일을 찾지 못했습니다. "
        "--claude-bin으로 경로를 직접 지정하거나 "
        "npm install -g @anthropic-ai/claude-code 로 설치하세요."
    )


def _extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체를 추출한다."""
    # 코드블록 안의 JSON 우선 시도
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if block:
        return json.loads(block.group(1))
    # 중괄호로 시작하는 첫 번째 JSON 객체 추출
    start = text.find("{")
    if start == -1:
        raise ValueError("JSON 객체를 찾을 수 없습니다.")
    # 중괄호 매칭으로 끝 위치 찾기
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("JSON 파싱 실패: 닫히지 않은 중괄호")


def _run_claude_list_once(texts: List[str], model: str, claude_bin: str) -> List[str]:
    n = len(texts)
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"아래 JSON 배열의 각 원소를 같은 순서로 한국어로 번역하라. (총 {n}개)\n"
        "규칙:\n"
        "- 원문 구조/정보량 유지\n"
        "- '...pe...' 표기는 그대로 유지\n"
        "- 원문 약호/고유어는 가능하면 병기\n"
        '- 반드시 다음 형식의 JSON만 출력하라. 설명문·코드블록·마크다운 없이 JSON 객체 하나만 출력:\n'
        '  {"translations": ["번역1", "번역2", ...]}\n\n'
        f"{json.dumps(texts, ensure_ascii=False)}"
    )

    cmd = [
        claude_bin,
        "--model", model,
        "--output-format", "text",
        "--print",
        prompt,
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude failed (exit={proc.returncode})")
    parsed = _extract_json(proc.stdout)
    arr = parsed.get("translations")
    if not isinstance(arr, list) or len(arr) != n:
        raise RuntimeError(
            f"translation length mismatch: expected={n} "
            f"got={len(arr) if isinstance(arr, list) else 'invalid'}"
        )
    return [str(x).strip() for x in arr]


def _run_claude_single_once(text: str, model: str, claude_bin: str) -> str:
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "아래 텍스트 1개를 한국어로 번역하라.\n"
        "규칙:\n"
        "- 원문 구조/정보량 유지\n"
        "- '...pe...' 표기는 그대로 유지\n"
        '- 반드시 다음 형식의 JSON만 출력하라. 설명문·코드블록·마크다운 없이 JSON 객체 하나만 출력:\n'
        '  {"translation": "번역 결과"}\n\n'
        f"{json.dumps(text, ensure_ascii=False)}"
    )
    cmd = [
        claude_bin,
        "--model", model,
        "--output-format", "text",
        "--print",
        prompt,
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude failed (single, exit={proc.returncode})")
    parsed = _extract_json(proc.stdout)
    val = parsed.get("translation")
    if not isinstance(val, str):
        raise RuntimeError("invalid single translation output")
    return val.strip()


def run_claude_translate_batch(
    texts: List[str], model: str, claude_bin: str, depth: int = 0, max_depth: int = 6
) -> List[str]:
    if not texts:
        return []

    last_err: Exception = RuntimeError("unknown")
    for attempt in range(1, 4):
        try:
            return _run_claude_list_once(texts, model, claude_bin)
        except Exception as e:
            last_err = e
            print(f"  [경고] 재시도 {attempt}/3 (size={len(texts)})", file=sys.stderr)
            time.sleep(1.0)

    # 배치 분할 재귀 폴백
    if len(texts) > 1 and depth < max_depth:
        mid = len(texts) // 2
        print(f"  [경고] 배치 분할: {len(texts)} -> {mid}+{len(texts)-mid}", file=sys.stderr)
        left = run_claude_translate_batch(texts[:mid], model, claude_bin, depth + 1, max_depth)
        right = run_claude_translate_batch(texts[mid:], model, claude_bin, depth + 1, max_depth)
        return left + right

    # 단일 항목 엄격 모드
    if len(texts) == 1:
        for attempt in range(1, 4):
            try:
                return [_run_claude_single_once(texts[0], model, claude_bin)]
            except Exception as e:
                last_err = e
                print(f"  [경고] 단일 재시도 {attempt}/3", file=sys.stderr)
                time.sleep(1.0)

    raise RuntimeError(f"번역 실패 (size={len(texts)}): {last_err}")


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
    if node.attrib.get("trans") == "false":
        node.attrib["trans"] = "true"
    for ch in list(node):
        set_trans_true(ch)


def find_target_lines(lines: List[str], start_line: int, limit: int) -> List[int]:
    targets = []
    for i, raw in enumerate(lines, start=1):
        if i < start_line:
            continue
        s = raw.strip()
        is_target = (
            (s.startswith("<p ") or s.startswith("<head ") or s.startswith("<trailer "))
            and 'trans="false"' in s
        )
        if is_target:
            targets.append(i)
            if len(targets) >= limit:
                break
    return targets


def main():
    ap = argparse.ArgumentParser(
        description="s0101m.mul.xml trans=false 단락을 claude CLI로 배치 번역하고 trans=true로 반영"
    )
    ap.add_argument("--items", type=int, required=True, help="처리할 단락 수 (예: 10, 20)")
    ap.add_argument("--batch-size", type=int, default=5, help="배치 크기 (기본 5)")
    ap.add_argument("--start-line", type=int, default=1, help="검색 시작 라인 (기본 1)")
    ap.add_argument("--model", default="claude-sonnet-4-6", help="claude model ID (기본 claude-sonnet-4-6)")
    ap.add_argument("--claude-bin", default="", help="claude 실행 파일 경로 (선택)")
    ap.add_argument("--sleep-seconds", type=float, default=2.0, help="배치 간 대기 시간(초), 기본 2.0")
    ap.add_argument("--dry-run", action="store_true", help="실제 수정 없이 대상만 출력")
    args = ap.parse_args()

    if args.items <= 0:
        raise SystemExit("--items must be > 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")

    claude_bin = resolve_claude_bin(args.claude_bin)

    lines = TARGET_XML.read_text(encoding="utf-8").splitlines(keepends=True)
    def _is_trans_false(raw: str) -> bool:
        s = raw.strip()
        return (
            (s.startswith("<p ") or s.startswith("<head ") or s.startswith("<trailer "))
            and 'trans="false"' in s
        )

    all_false = [i for i, raw in enumerate(lines, start=1) if _is_trans_false(raw)]
    targets = find_target_lines(lines, args.start_line, args.items)
    if not targets:
        print("대상 단락이 없습니다.")
        return

    print(f"파일: {TARGET_XML}")
    print(f"전체 미번역 단락(p trans=false): {len(all_false)}")
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
        outs = run_claude_translate_batch(texts, args.model, claude_bin)

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
        TARGET_XML.write_text("".join(lines), encoding="utf-8")
        print("  -> saved to file")
        if bidx < len(batches) and args.sleep_seconds > 0:
            print(f"  -> sleep {args.sleep_seconds:.1f}s before next batch")
            time.sleep(args.sleep_seconds)

    after_lines = TARGET_XML.read_text(encoding="utf-8").splitlines()
    remain_false = sum(1 for raw in after_lines if _is_trans_false(raw))
    print("")
    print("[완료 요약]")
    print(f"- 시작 라인: {first_done}")
    print(f"- 종료 라인: {last_done}")
    print(f"- 처리 단락 수: {done}")
    print(f"- 남은 미번역 단락(trans=false): {remain_false}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
