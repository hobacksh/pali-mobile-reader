#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from xml.dom import minidom


SYSTEM_PROMPT = (
    "당신은 신심있는 테라와다 불자로서, 한국어와 Pali에 능통한 번역가이다. "
    "주어진 빠알리 텍스트를 한국어로 번역한다. 경전에 맞는 자연스러운 문장을 사용한다."
)


def decode_xml_bytes(raw: bytes):
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16le"), "utf-16le"
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16be"), "utf-16be"
    return raw.decode("utf-8"), "utf-8"


def encode_xml_text(text: str, enc: str):
    if enc == "utf-16le":
        return b"\xff\xfe" + text.encode("utf-16le")
    if enc == "utf-16be":
        return b"\xfe\xff" + text.encode("utf-16be")
    return text.encode("utf-8")


def is_translatable(s: str):
    t = s.strip()
    if not t:
        return False
    if re.fullmatch(r"[\d\W_]+", t, flags=re.UNICODE):
        return False
    return True


def collect_text_nodes(node, bag):
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            if is_translatable(child.data):
                bag.append(child)
        elif child.nodeType == child.ELEMENT_NODE:
            if child.tagName.lower() == "pb":
                continue
            collect_text_nodes(child, bag)


def run_codex_translate_batch(texts, model=None, depth=0):
    if not texts:
        return []
    if depth > 5:
        raise RuntimeError(f"Exceeded retry depth while translating batch of {len(texts)}")
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        schema_path = td_path / "schema.json"
        out_path = td_path / "out.json"

        schema = {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        }
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        user_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "다음 JSON 배열의 각 원소(빠알리/로마자 텍스트)를 같은 순서로 한국어로 번역하라.\n"
            "반드시 JSON 객체 하나만 출력하고, 형식은 {\"translations\": string[]} 이어야 한다.\n"
            "설명/코드블록/마크다운을 넣지 마라.\n\n"
            f"{json.dumps(texts, ensure_ascii=False)}"
        )

        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(out_path),
        ]
        if model:
            cmd.extend(["-m", model])
        cmd.append("-")

        proc = subprocess.run(
            cmd,
            input=user_prompt,
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
            raise RuntimeError("codex output file missing.")

        raw = out_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(raw)
        arr = parsed.get("translations") if isinstance(parsed, dict) else None
        if not isinstance(arr, list):
            raise RuntimeError("codex output is not {translations: string[]}.")
        if len(arr) != len(texts):
            if len(texts) == 1:
                raise RuntimeError(f"Length mismatch: expected 1, got {len(arr)}")
            mid = len(texts) // 2
            print(
                f"  ! length mismatch ({len(arr)}/{len(texts)}), "
                f"retry split batch: {mid} + {len(texts)-mid}"
            )
            left = run_codex_translate_batch(texts[:mid], model=model, depth=depth + 1)
            right = run_codex_translate_batch(texts[mid:], model=model, depth=depth + 1)
            return left + right
        return [str(x) for x in arr]


def split_overlong_sentence(text, max_chars):
    if len(text) <= max_chars:
        return [text]
    parts = []
    rest = text.strip()
    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars + 1)
        if cut < int(max_chars * 0.5):
            cut = max_chars
        piece = rest[:cut].strip()
        if piece:
            parts.append(piece)
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return parts


def split_paragraph_to_pieces(paragraph, max_chars):
    text = paragraph.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentence_pattern = r"[^.!?;:।॥\n]+[.!?;:।॥\n]*"
    raw_sentences = [m.group(0).strip() for m in re.finditer(sentence_pattern, text) if m.group(0).strip()]
    if not raw_sentences:
        raw_sentences = [text]

    pieces = []
    current = ""
    for sent in raw_sentences:
        if len(sent) > max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            pieces.extend(split_overlong_sentence(sent, max_chars))
            continue

        if not current:
            current = sent
        elif len(current) + 1 + len(sent) <= max_chars:
            current = f"{current} {sent}"
        else:
            pieces.append(current.strip())
            current = sent
    if current:
        pieces.append(current.strip())
    return pieces


def build_translation_items(paragraphs, max_batch_chars):
    items = []
    for node_idx, para in enumerate(paragraphs):
        parts = split_paragraph_to_pieces(para, max_batch_chars)
        if not parts:
            parts = [para]
        for piece_idx, piece in enumerate(parts):
            items.append(
                {
                    "node_idx": node_idx,
                    "piece_idx": piece_idx,
                    "text": piece,
                }
            )
    return items


def build_batches(items, max_batch_chars):
    batches = []
    current = []
    current_chars = 0
    for item in items:
        tlen = len(item["text"])
        if current and current_chars + tlen > max_batch_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += tlen
    if current:
        batches.append(current)
    return batches


def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class Logger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str):
        line = f"[{now_iso()}] {msg}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def atomic_write_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_state(state_path: Path, state_obj: dict):
    atomic_write_text(state_path, json.dumps(state_obj, ensure_ascii=False, indent=2))


def load_state(state_path: Path):
    if not state_path.exists():
        return None
    return json.loads(state_path.read_text(encoding="utf-8"))


def build_node_item_ids(items, total_nodes):
    node_item_ids = {i: [] for i in range(total_nodes)}
    for item in items:
        node_item_ids[item["node_idx"]].append(item["item_id"])
    return node_item_ids


def write_partial_output(
    dom,
    nodes,
    originals,
    node_item_ids,
    translated_by_item,
    output_path: Path,
    enc: str,
):
    for node_idx, node in enumerate(nodes):
        item_ids = node_item_ids.get(node_idx, [])
        if not item_ids:
            node.data = originals[node_idx]
            continue
        translated_pieces = []
        all_done = True
        for item_id in item_ids:
            t = translated_by_item[item_id]
            if t is None:
                all_done = False
                break
            translated_pieces.append(str(t).strip())
        if all_done:
            node.data = " ".join(x for x in translated_pieces if x).strip()
        else:
            node.data = originals[node_idx]

    out_file = output_path.with_suffix(output_path.suffix + ".partial")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(encode_xml_text(dom.toxml(), enc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input XML path")
    parser.add_argument("--output", required=True, help="Output XML path")
    parser.add_argument("--model", default=None, help="Optional codex model (e.g. gpt-5)")
    parser.add_argument(
        "--max-batch-chars",
        type=int,
        default=5000,
        help="Max characters per translation batch. Paragraphs are accumulated until this limit.",
    )
    parser.add_argument("--state-file", default=None, help="Checkpoint state JSON path")
    parser.add_argument("--log-file", default=None, help="Progress log file path")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing checkpoint and start from scratch")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    state_path = Path(args.state_file) if args.state_file else Path(str(out_path) + ".state.json")
    log_path = Path(args.log_file) if args.log_file else Path(str(out_path) + ".progress.log")
    logger = Logger(log_path)

    raw = in_path.read_bytes()
    xml_text, enc = decode_xml_bytes(raw)
    dom = minidom.parseString(xml_text)

    nodes = []
    collect_text_nodes(dom, nodes)
    originals = [n.data for n in nodes]
    total_nodes = len(originals)
    logger.log(f"collected text nodes: {total_nodes}")

    items = build_translation_items(originals, args.max_batch_chars)
    for item_id, item in enumerate(items):
        item["item_id"] = item_id
    batches = build_batches(items, args.max_batch_chars)
    node_item_ids = build_node_item_ids(items, total_nodes)
    total_items = len(items)
    logger.log(
        f"planned translation items: {total_items} "
        f"(paragraph splits included), batches: {len(batches)}, "
        f"max_batch_chars={args.max_batch_chars}"
    )

    started = time.time()
    translated_by_item = [None] * total_items

    run_sig = {
        "input": str(in_path.resolve()),
        "output": str(out_path.resolve()),
        "model": args.model or "",
        "max_batch_chars": args.max_batch_chars,
        "total_nodes": total_nodes,
        "total_items": total_items,
    }

    if not args.no_resume:
        prev = load_state(state_path)
        if prev:
            prev_sig = prev.get("run_sig", {})
            prev_arr = prev.get("translated_by_item")
            if prev_sig == run_sig and isinstance(prev_arr, list) and len(prev_arr) == total_items:
                translated_by_item = prev_arr
                done_prev = sum(1 for x in translated_by_item if x is not None)
                logger.log(f"resumed from checkpoint: {done_prev}/{total_items} items done")
            else:
                logger.log("checkpoint found but incompatible with current run config; starting fresh")

    def checkpoint():
        processed = sum(1 for x in translated_by_item if x is not None)
        state_obj = {
            "version": 1,
            "updated_at": now_iso(),
            "run_sig": run_sig,
            "processed_items": processed,
            "translated_by_item": translated_by_item,
        }
        save_state(state_path, state_obj)
        write_partial_output(dom, nodes, originals, node_item_ids, translated_by_item, out_path, enc)

    try:
        for batch_idx, batch in enumerate(batches, start=1):
            pending = [x for x in batch if translated_by_item[x["item_id"]] is None]
            if not pending:
                continue
            batch_texts = [x["text"] for x in pending]
            processed_items = sum(1 for x in translated_by_item if x is not None)
            batch_chars = sum(len(x) for x in batch_texts)
            elapsed = time.time() - started
            avg_per_item = (elapsed / processed_items) if processed_items else 0
            remaining_items = max(total_items - processed_items, 0)
            eta = avg_per_item * remaining_items
            pct = (processed_items / total_items * 100.0) if total_items else 100.0
            logger.log(
                f"[batch {batch_idx}/{len(batches)}] "
                f"{pct:5.1f}% | items={len(batch_texts)} | chars={batch_chars} | "
                f"elapsed={format_seconds(elapsed)} | eta={format_seconds(eta)}"
            )
            batch_started = time.time()
            batch_translated = run_codex_translate_batch(batch_texts, args.model)
            for item, out_text in zip(pending, batch_translated):
                translated_by_item[item["item_id"]] = out_text.strip()
            processed_items = sum(1 for x in translated_by_item if x is not None)
            total_elapsed = time.time() - started
            done_pct = (processed_items / total_items * 100.0) if total_items else 100.0
            avg_done = (total_elapsed / processed_items) if processed_items else 0
            eta_done = avg_done * max(total_items - processed_items, 0)
            logger.log(
                f"  -> batch done {processed_items}/{total_items} ({done_pct:5.1f}%) | "
                f"batch_time={format_seconds(time.time()-batch_started)} | "
                f"elapsed={format_seconds(total_elapsed)} | eta={format_seconds(eta_done)}"
            )
            checkpoint()
    except KeyboardInterrupt:
        checkpoint()
        logger.log("interrupted: checkpoint and partial output saved")
        raise

    for node_idx, node in enumerate(nodes):
        item_ids = node_item_ids.get(node_idx, [])
        if not item_ids:
            continue
        merged = " ".join((translated_by_item[item_id] or "").strip() for item_id in item_ids).strip()
        if merged:
            node.data = merged

    rendered = dom.toxml()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(encode_xml_text(rendered, enc))
    total_elapsed = time.time() - started
    logger.log(f"written: {out_path}")
    logger.log(f"total elapsed: {format_seconds(total_elapsed)}")


def format_seconds(sec):
    sec = int(max(sec, 0))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
