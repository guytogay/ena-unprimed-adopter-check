#!/usr/bin/env python3
"""Shared fail-closed reader for JSONL input sources used by ENA reference tools."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ena_text import read_text


class JsonlSourceError(ValueError):
    """Raised when a declared JSONL source cannot be safely consumed."""


@dataclass(frozen=True)
class JsonlSource:
    reference: str
    text: str
    records: list[object]
    line_numbers: list[int]
    sha256: str


def load_jsonl_source(path: str | Path) -> JsonlSource:
    p = Path(path)
    if not p.exists():
        raise JsonlSourceError(f"input source not found: {p}")
    if not p.is_file():
        raise JsonlSourceError(f"input source is not a file: {p}")

    try:
        text = read_text(p)
    except (OSError, UnicodeError) as exc:
        raise JsonlSourceError(f"cannot read input source {p}: {exc}") from exc

    records: list[object] = []
    line_numbers: list[int] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            records.append(json.loads(raw))
            line_numbers.append(line_no)
        except json.JSONDecodeError as exc:
            raise JsonlSourceError(
                f"invalid JSONL in {p} at line {line_no}: {exc.msg}"
            ) from exc

    return JsonlSource(
        reference=str(p),
        text=text,
        records=records,
        line_numbers=line_numbers,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
