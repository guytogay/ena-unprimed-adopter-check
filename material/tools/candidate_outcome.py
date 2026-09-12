#!/usr/bin/env python3
"""Persist an already-made candidate outcome without making the decision itself."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from ena_actor import actor_block, resolve_actor
from ena_home import EnaHomeError, require_initialized_home, resolve_home_path
from ena_text import read_text

OUTCOMES = ("retain", "revise", "reject", "restore")
UNRESOLVED = {"", "unknown", "null", "none", "~"}


def unresolved(value: object) -> bool:
    return not isinstance(value, str) or value.strip().lower() in UNRESOLVED


def candidate_dirs(home: Path) -> tuple[Path, Path, Path]:
    speculative = resolve_home_path(
        home,
        "evolution.speculative_candidates",
        default_relative="evolution/candidates/speculative",
    )
    selected = resolve_home_path(
        home,
        "evolution.selected_candidates",
        default_relative="evolution/candidates/selected",
    )
    outcomes = (selected.parent / "outcomes").resolve()
    try:
        outcomes.relative_to(home.resolve())
    except ValueError as exc:
        raise EnaHomeError(
            f"derived candidate outcomes path resolves outside the active ENA home: {outcomes}"
        ) from exc
    return speculative, selected, outcomes


def load_source(path: Path, speculative: Path) -> tuple[dict[str, object], str, Path]:
    source = path.expanduser().resolve()
    if source.parent != speculative.resolve():
        raise ValueError(f"source candidate must be directly under {speculative.resolve()}")
    if not source.is_file():
        raise ValueError(f"source candidate not found: {source}")
    try:
        text = read_text(source)
        record = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot safely read source candidate {source}: {exc}") from exc
    if not isinstance(record, dict):
        raise ValueError("source candidate must be a JSON object")
    for key in ("id", "origin", "candidate", "reality_check"):
        if unresolved(record.get(key)):
            raise ValueError(f"source candidate {key} is unresolved")
    if record.get("truth_status") != "speculative":
        raise ValueError("source candidate truth_status must be 'speculative'")
    return record, hashlib.sha256(text.encode("utf-8")).hexdigest(), source


def existing_decision(selected: Path, outcomes: Path, candidate_id: str) -> Path | None:
    for bucket, directory in (("selected", selected), ("outcomes", outcomes)):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            try:
                record = json.loads(read_text(path))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"cannot safely inspect existing candidate decision {path}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"existing candidate decision is not a JSON object: {path}")
            recorded = record.get("candidate_id")
            legacy_selected = bucket == "selected" and record.get("id") == candidate_id
            if recorded == candidate_id or legacy_selected:
                return path
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="Record a candidate outcome already decided elsewhere.")
    p.add_argument("source", type=Path)
    p.add_argument("--home", default="~/.ena")
    p.add_argument("--outcome", required=True, choices=OUTCOMES)
    p.add_argument("--evidence", action="append", required=True)
    p.add_argument("--boundary", action="append", default=[])
    p.add_argument("--decided-by", required=True)
    args = p.parse_args()

    home = Path(args.home).expanduser().resolve()
    try:
        tz, tz_name = require_initialized_home(home)
        speculative, selected, outcomes = candidate_dirs(home)
    except EnaHomeError as exc:
        print(f"ENA candidate outcome: ERROR: {exc}", file=sys.stderr)
        return 2

    evidence = [x.strip() for x in args.evidence if x and x.strip()]
    if unresolved(args.decided_by) or not evidence or any(x.lower() in UNRESOLVED for x in evidence):
        print("ENA candidate outcome: ERROR: decided-by and evidence must be resolved", file=sys.stderr)
        return 2

    try:
        candidate, digest, source = load_source(args.source, speculative)
        prior = existing_decision(selected, outcomes, str(candidate["id"]))
    except ValueError as exc:
        print(f"ENA candidate outcome: ERROR: {exc}", file=sys.stderr)
        return 2
    if prior is not None:
        print(
            f"ENA candidate outcome: ERROR: candidate already has a recorded outcome: {prior}",
            file=sys.stderr,
        )
        return 2

    now = datetime.now(tz)
    decision_id = f"decision-{uuid.uuid4().hex[:12]}"
    out_dir = selected if args.outcome == "retain" else outcomes
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{now.strftime('%Y%m%dT%H%M%S%f%z')}__{decision_id}.json"

    snapshot = {key: candidate.get(key) for key in (
        "created_at", "origin", "truth_status", "source_fragments", "candidate", "reality_check"
    )}
    record = {
        "schema_version": "0.1",
        "id": decision_id,
        "candidate_id": candidate["id"],
        "decided_at": now.isoformat(timespec="microseconds"),
        "timezone": tz_name,
        "outcome": args.outcome,
        "selection_status": "selected" if args.outcome == "retain" else "not_selected",
        "decided_by": args.decided_by.strip(),
        "evidence_refs": evidence,
        "boundaries": [x.strip() for x in args.boundary if x and x.strip()],
        "source": {
            "reference": source.relative_to(home).as_posix(),
            "sha256": digest,
        },
        "actor": actor_block(resolve_actor()),
        "candidate_snapshot": snapshot,
    }

    try:
        with target.open("x", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except (FileExistsError, OSError) as exc:
        print(f"ENA candidate outcome: ERROR: cannot create {target}: {exc}", file=sys.stderr)
        return 2

    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
