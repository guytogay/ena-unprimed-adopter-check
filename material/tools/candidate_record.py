#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from ena_actor import actor_block, resolve_actor
from ena_home import EnaHomeError, require_initialized_home, resolve_home_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--home", default="~/.ena")
    p.add_argument("--origin", required=True, choices=("dream", "sleep", "work", "other"))
    p.add_argument("--candidate", required=True)
    p.add_argument("--reality-check", required=True)
    p.add_argument("--source", action="append", default=[])
    args = p.parse_args()

    home = Path(args.home).expanduser().resolve()
    try:
        tz, tz_name = require_initialized_home(home)
        out_dir = resolve_home_path(
            home,
            "evolution.speculative_candidates",
            default_relative="evolution/candidates/speculative",
        )
    except EnaHomeError as exc:
        print(f"ENA candidate: ERROR: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz)
    candidate_id = f"candidate-{uuid.uuid4().hex[:12]}"
    stamp = now.strftime("%Y%m%dT%H%M%S%f%z")
    target = out_dir / f"{stamp}__{candidate_id}.json"
    record = {
        "schema_version": "0.1",
        "id": candidate_id,
        "created_at": now.isoformat(timespec="microseconds"),
        "timezone": tz_name,
        "origin": args.origin,
        "truth_status": "speculative",
        "source_fragments": args.source,
        "candidate": args.candidate,
        "reality_check": args.reality_check,
        "actor": actor_block(resolve_actor()),
        "outcome": None,
    }

    try:
        with target.open("x", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except FileExistsError:
        print(f"ENA candidate: ERROR: refusing to overwrite existing candidate artifact: {target}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ENA candidate: ERROR: cannot write {target}: {exc}", file=sys.stderr)
        return 2

    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
