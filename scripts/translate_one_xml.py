#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path
from xml.dom import minidom
from urllib import request


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
    # Keep page markers, punctuation-only, numbers unchanged.
    if re.fullmatch(r"[\d\W_]+", t, flags=re.UNICODE):
        return False
    return True


def collect_text_nodes(node, bag):
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            if is_translatable(child.data):
                bag.append(child)
        elif child.nodeType == child.ELEMENT_NODE:
            # Keep pb markers untouched.
            if child.tagName.lower() == "pb":
                continue
            collect_text_nodes(child, bag)


def call_openai_batch(texts, model):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "아래 JSON 배열의 각 문자열을 같은 순서로 한국어로 번역해라. "
                    "반드시 JSON 배열(string[])만 출력해라.\n\n"
                    f"{json.dumps(texts, ensure_ascii=False)}"
                ),
            },
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    output_text = data.get("output_text", "").strip()
    if not output_text:
        raise RuntimeError("No output_text in API response.")
    try:
        arr = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model did not return JSON array: {output_text[:500]}") from exc
    if not isinstance(arr, list) or len(arr) != len(texts):
        raise RuntimeError("Translated array length mismatch.")
    return [str(x) for x in arr]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input XML path")
    parser.add_argument("--output", required=True, help="Output XML path")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--batch-size", type=int, default=80)
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    raw = in_path.read_bytes()
    xml_text, enc = decode_xml_bytes(raw)
    dom = minidom.parseString(xml_text)

    nodes = []
    collect_text_nodes(dom, nodes)
    originals = [n.data for n in nodes]
    print(f"collected text nodes: {len(originals)}")

    translated = []
    for i in range(0, len(originals), args.batch_size):
        chunk = originals[i : i + args.batch_size]
        print(f"translating chunk {i}..{i + len(chunk) - 1}")
        translated.extend(call_openai_batch(chunk, args.model))

    for node, text in zip(nodes, translated):
        node.data = text

    rendered = dom.toxml()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(encode_xml_text(rendered, enc))
    print(f"written: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
