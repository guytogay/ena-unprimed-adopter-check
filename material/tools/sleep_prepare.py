#!/usr/bin/env python3
"""Prepare a bounded Sleep input bundle from JSONL experience and memory records."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ena_text import EnaTextWriteError, write_text
from jsonl_source import JsonlSourceError, load_jsonl_source


def bounded_source(reference: str, role: str, max_records: int) -> tuple[list[object], dict[str, object]]:
    source = load_jsonl_source(reference)
    records = source.records
    selected = records[-max_records:] if max_records > 0 else []
    meta = {
        "role": role,
        "reference": source.reference,
        "sha256": source.sha256,
        "source_record_count": len(records),
        "selected_record_count": len(selected),
        "selection": {
            "strategy": "tail",
            "max_records": max_records,
        },
    }
    return selected, meta


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Build a bounded Sleep transport bundle. The reference tail selection is conservative; "
            "it is not a complete Sleep retrieval policy for older relevant memory/knowledge."
        )
    )
    p.add_argument("--experience", required=True)
    p.add_argument("--memory", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--max-experience", type=int, default=50)
    p.add_argument("--max-memory", type=int, default=80)
    args = p.parse_args()

    if args.max_experience < 0 or args.max_memory < 0:
        raise SystemExit("--max-experience and --max-memory must be >= 0")

    try:
        experience, experience_meta = bounded_source(args.experience, "experience", args.max_experience)
        memory, memory_meta = bounded_source(args.memory, "memory", args.max_memory)
    except JsonlSourceError as exc:
        print(f"ENA Sleep input: ERROR: {exc}", file=sys.stderr)
        return 2

    bundle = {
        "task": "sleep_consolidation",
        "input": {
            "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "sources": [experience_meta, memory_meta],
        },
        "instructions": [
            "Find repetition, duplication, fragmentation, conflict, staleness, overreach, reusable procedures, boundaries, unresolved questions, and missing links.",
            "Produce a consolidation plan before changing durable memory.",
            "Preserve provenance, counterexamples, and uncertainty.",
            "Prefer no change or a narrower memory when evidence is ambiguous.",
        ],
        "experience": experience,
        "memory": memory,
    }
    target = Path(args.output)
    try:
        write_text(target, json.dumps(bundle, indent=2, ensure_ascii=False))
    except EnaTextWriteError as exc:
        print(f"ENA Sleep input: ERROR: {exc}", file=sys.stderr)
        return 2
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
