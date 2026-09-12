#!/usr/bin/env python3
"""Experimental Dream sampler using biased randomness and optional associative distance."""

from __future__ import annotations

import argparse
import json
import math
import random
import secrets
import sys
from datetime import datetime
from pathlib import Path

from ena_text import EnaTextWriteError, write_text
from jsonl_source import JsonlSourceError, load_jsonl_source


def parse_time(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def cosine(a, b):
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b) or not a:
        return None
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    if not na or not nb:
        return None
    return dot / (na * nb)


def choose(pool, used, rng):
    options = [x for x in pool if x.get("id") not in used]
    if not options:
        return None
    item = rng.choice(options)
    used.add(item.get("id"))
    return item


def middle_distance_pool(anchor, records):
    scored = []
    for item in records:
        if item.get("id") == anchor.get("id"):
            continue
        score = cosine(anchor.get("embedding"), item.get("embedding"))
        if score is not None:
            scored.append((score, item))
    if len(scored) >= 4:
        scored.sort(key=lambda x: x[0], reverse=True)
        lo = max(1, int(len(scored) * 0.25))
        hi = max(lo + 1, int(len(scored) * 0.75))
        return [item for _, item in scored[lo:hi]]

    domain = anchor.get("domain")
    source = anchor.get("source_type")
    distant = [
        item
        for item in records
        if item.get("id") != anchor.get("id")
        and (item.get("domain") != domain or item.get("source_type") != source)
    ]
    return distant or [item for item in records if item.get("id") != anchor.get("id")]


def main() -> int:
    p = argparse.ArgumentParser(
        description="Reference Dream sampler. Defaults are experimental field parameters, not ENA requirements."
    )
    p.add_argument("--memory", required=True, help="JSONL records")
    p.add_argument("--output", required=True)
    p.add_argument("--mode", choices=("free", "problem-guided"), default="free")
    p.add_argument("--anchor-id", help="Required for problem-guided mode")
    p.add_argument("--seed", type=int)
    p.add_argument("--count", type=int, default=6, help="Experimental default: 6 source fragments")
    p.add_argument(
        "--random-jump-probability",
        type=float,
        default=0.10,
        help="Experimental default: 0.10",
    )
    args = p.parse_args()

    try:
        source = load_jsonl_source(args.memory)
    except JsonlSourceError as exc:
        print(f"ENA Dream sampler: ERROR: {exc}", file=sys.stderr)
        return 2

    records = source.records
    if any(not isinstance(item, dict) for item in records):
        print("ENA Dream sampler: ERROR: every input record must be a JSON object", file=sys.stderr)
        return 2
    if len(records) < 2:
        raise SystemExit("Need at least two memory records")

    seed = args.seed if args.seed is not None else secrets.randbits(64)
    rng = random.Random(seed)

    by_id = {x.get("id"): x for x in records}
    unresolved = [x for x in records if x.get("unresolved")]
    by_time = sorted(records, key=lambda x: parse_time(x.get("timestamp")))
    quarter = max(1, len(records) // 4)

    if args.mode == "problem-guided":
        if not args.anchor_id or args.anchor_id not in by_id:
            raise SystemExit("problem-guided mode requires --anchor-id matching a memory record")
        anchor = by_id[args.anchor_id]
    else:
        anchor = rng.choice(unresolved or by_time[-quarter:])

    pools = {
        "recent": by_time[-quarter:],
        "old": by_time[:quarter],
        "underused": sorted(records, key=lambda x: x.get("retrieval_count", 0))[:quarter],
        "external_or_unresolved": unresolved
        or [x for x in records if x.get("source_type") in {"user", "document", "a2a", "external"}],
        "distant": middle_distance_pool(anchor, records),
        "salient": sorted(records, key=lambda x: x.get("salience", 0), reverse=True)[:quarter],
        "random": records,
    }

    used = {anchor.get("id")}
    selected = [{"pool": "anchor", "memory": anchor}]
    order = ["recent", "old", "underused", "external_or_unresolved", "distant", "salient"]
    rng.shuffle(order)

    for label in order:
        if len(selected) >= min(args.count, len(records)):
            break
        item = choose(pools[label], used, rng)
        if item is not None:
            selected.append({"pool": label, "memory": item})

    if rng.random() < max(0.0, min(1.0, args.random_jump_probability)) and len(selected) < min(args.count, len(records)):
        item = choose(pools["random"], used, rng)
        if item is not None:
            selected.append({"pool": "random_jump", "memory": item})

    while len(selected) < min(args.count, len(records)):
        item = choose(pools["random"], used, rng)
        if item is None:
            break
        selected.append({"pool": "random", "memory": item})

    output = {
        "experimental_parameters": True,
        "mode": args.mode,
        "seed": seed,
        "input": {
            "reference": source.reference,
            "sha256": source.sha256,
            "record_count": len(records),
        },
        "anchor_id": anchor.get("id") if args.mode == "problem-guided" else None,
        "sampled_anchor_id": anchor.get("id") if args.mode == "free" else None,
        "count": args.count,
        "random_jump_probability": args.random_jump_probability,
        "truth_status": "speculative_input",
        "fragments": selected,
    }
    target = Path(args.output)
    try:
        write_text(target, json.dumps(output, indent=2, ensure_ascii=False))
    except EnaTextWriteError as exc:
        print(f"ENA Dream sampler: ERROR: {exc}", file=sys.stderr)
        return 2
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
