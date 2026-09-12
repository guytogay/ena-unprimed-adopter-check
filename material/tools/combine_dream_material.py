#!/usr/bin/env python3
"""Combine memory, knowledge and capability JSONL into one Dream input file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ena_text import EnaTextWriteError, write_text
from jsonl_source import JsonlSourceError, load_jsonl_source


def read_jsonl(path: str, material_type: str):
    source = load_jsonl_source(path)
    records = []
    for item in source.records:
        if not isinstance(item, dict):
            raise JsonlSourceError(f"Dream material record in {source.reference} must be a JSON object")
        item = dict(item)
        item.setdefault("material_type", material_type)
        records.append(item)
    return records


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--memory", required=True)
    p.add_argument("--knowledge")
    p.add_argument("--capabilities")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    try:
        records = read_jsonl(args.memory, "memory")
        if args.knowledge:
            records.extend(read_jsonl(args.knowledge, "knowledge"))
        if args.capabilities:
            records.extend(read_jsonl(args.capabilities, "capability"))
    except JsonlSourceError as exc:
        print(f"ENA Dream material: ERROR: {exc}", file=sys.stderr)
        return 2

    seen = set()
    for item in records:
        record_id = item.get("id")
        if not record_id:
            raise SystemExit("Every Dream material record needs an id")
        if record_id in seen:
            raise SystemExit(f"Duplicate Dream material id: {record_id}")
        seen.add(record_id)

    out = Path(args.output)
    try:
        write_text(out, "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records))
    except EnaTextWriteError as exc:
        print(f"ENA Dream material: ERROR: {exc}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
