#!/usr/bin/env python3
"""Strict reader for ENA-owned control YAML.

This is intentionally not a general YAML parser. It accepts mappings and
scalar values using two-space indentation, including nested mappings emitted
by ENA reference tools. Sequence syntax and multiline/block scalars fail
closed instead of being silently misread.
"""

from __future__ import annotations

import re
from typing import Any


class ControlYamlError(ValueError):
    pass


_KEY = re.compile(r"^[A-Za-z0-9_.-]+$")
_UNKNOWN_PREFIX = re.compile(r"^unknown(?![A-Za-z0-9])", re.IGNORECASE)


def _clean_scalar(raw: str) -> str:
    value = raw.strip()
    if value.startswith(("|", ">")):
        raise ControlYamlError("multiline/block scalars are not supported in ENA control YAML")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_control_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    containers: dict[int, dict[str, Any]] = {0: root}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        prefix = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in prefix:
            raise ControlYamlError(f"line {lineno}: tabs are not allowed for indentation")

        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ControlYamlError(f"line {lineno}: indentation must use multiples of two spaces")
        depth = indent // 2
        parent = containers.get(depth)
        if parent is None:
            raise ControlYamlError(f"line {lineno}: indentation jumps over a missing parent mapping")

        line = raw[indent:]
        if line.startswith("- ") or line == "-":
            raise ControlYamlError(f"line {lineno}: sequence syntax is not supported")
        if ":" not in line:
            raise ControlYamlError(f"line {lineno}: expected key: value")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not _KEY.fullmatch(key):
            raise ControlYamlError(f"line {lineno}: unsupported key {key!r}")
        if key in parent:
            raise ControlYamlError(f"line {lineno}: duplicate key {key!r}")

        value = _clean_scalar(raw_value)
        for stale_depth in [item for item in containers if item > depth]:
            del containers[stale_depth]

        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            containers[depth + 1] = child
        else:
            parent[key] = value

    return root


def scalar(data: dict[str, Any], key: str, *, section: str | None = None) -> str | None:
    value: Any
    if section is None:
        value = data.get(key)
    else:
        parent = data.get(section)
        if not isinstance(parent, dict):
            return None
        value = parent.get(key)
    return value if isinstance(value, str) else None


def missing(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    if normalized.lower() in {"", "null", "none", "~", "[]"}:
        return True
    # `UNKNOWN` may carry a human- or machine-style explanation while remaining
    # explicitly unresolved. Treat it as a leading token when the next character
    # is not alphanumeric; values such as `UNKNOWNX` and `unknownstash-backup`
    # remain ordinary known strings.
    return bool(_UNKNOWN_PREFIX.match(normalized))
