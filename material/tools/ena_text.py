#!/usr/bin/env python3
"""Read and write ENA-owned UTF-8 text through one Host-facing boundary.

Reads tolerate a leading UTF-8 BOM because some Host-native editors and shells
write one by default. Writes create missing parent directories and surface
filesystem/encoding failures to callers instead of leaking interpreter
tracebacks from reference tools.
"""

from __future__ import annotations

from pathlib import Path


class EnaTextWriteError(Exception):
    """An ENA-owned text output could not be written."""


def read_text(path: Path) -> str:
    """Return the text of an ENA-owned file, tolerating a leading UTF-8 BOM."""
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str, *, exclusive: bool = False) -> None:
    """Write UTF-8 text, creating parents and converting write failures.

    `exclusive=True` refuses to overwrite an existing target.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "x" if exclusive else "w"
        with target.open(mode, encoding="utf-8", newline="") as fh:
            fh.write(text)
    except (OSError, UnicodeError) as exc:
        raise EnaTextWriteError(f"cannot write {target}: {exc}") from exc
