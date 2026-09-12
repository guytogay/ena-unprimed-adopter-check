#!/usr/bin/env python3
"""Shared boundaries for initialized ENA homes, clocks, and ENA-owned paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from control_yaml import ControlYamlError, missing, parse_control_yaml, scalar
from ena_text import read_text
from timezone_utils import TimezoneUnavailable, load_timezone

INIT_HINT = "Run tools/ena_init.py first or pass --home to an initialized ENA home."
PACKAGE_LAYOUT_HINT = (
    "A SAFE-CHANGE package must live directly under the owning ENA home's configured "
    "recovery.changes directory; create it with tools/change_scaffold.py."
)


class EnaHomeError(ValueError):
    """Raised when an ENA home cannot supply a fact a maintaining tool requires."""


def read_control(path: Path) -> dict[str, object]:
    """Read one ENA control file, failing closed with an actionable error."""
    try:
        return parse_control_yaml(read_text(path))
    except (OSError, UnicodeError, ControlYamlError) as exc:
        raise EnaHomeError(f"{path.name} cannot be safely parsed: {exc}") from exc


def value_at(data: dict[str, Any], dotted: str) -> str | None:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current if isinstance(current, str) else None


def _resolve_against_home(home: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (home / candidate).resolve()


def _require_inside_home(home: Path, target: Path, field: str) -> Path:
    try:
        target.relative_to(home)
    except ValueError as exc:
        raise EnaHomeError(
            f"ENA.yaml {field} resolves outside the active ENA home: {target}. "
            "ENA-owned writable state paths must stay inside the active home."
        ) from exc
    return target


def validate_declared_home(home: Path, data: dict[str, object] | None = None) -> None:
    """Reject a known `ena_home` that points somewhere other than the active home.

    New homes store `ena_home: .` so they are relocatable. Legacy absolute values
    remain compatible only while they resolve to the active control-file parent.
    This prevents a copied/moved home from later following stale absolute pointers
    and writing durable state back into its old location.
    """
    home = Path(home).expanduser().resolve()
    config = home / "ENA.yaml"
    config_data = data if data is not None else read_control(config)
    declared = scalar(config_data, "ena_home")
    if missing(declared):
        return
    resolved = _resolve_against_home(home, declared or "")
    if resolved != home:
        raise EnaHomeError(
            "ENA home relocation mismatch: ENA.yaml declares "
            f"ena_home {declared!r} -> {resolved}, but the active home is {home}. "
            "Reconcile the moved/copied home before running a maintaining ENA tool."
        )


def resolve_home_path(home: Path, dotted: str, *, default_relative: str | None = None) -> Path:
    """Resolve one ENA-owned machine path against the active home.

    Relative values are relative to the active ENA home, never process CWD.
    Legacy absolute values are accepted only when they remain inside this same
    active home. Missing legacy fields may use an explicit compatibility default.
    """
    home = Path(home).expanduser().resolve()
    config = home / "ENA.yaml"
    if not config.is_file():
        raise EnaHomeError(f"ENA home is not initialized: missing {config}. {INIT_HINT}")
    data = read_control(config)
    validate_declared_home(home, data)
    raw = value_at(data, dotted)
    if missing(raw):
        if default_relative is None:
            raise EnaHomeError(f"ENA.yaml {dotted} is unresolved")
        raw = default_relative
    target = _resolve_against_home(home, raw or "")
    return _require_inside_home(home, target, dotted)


def require_initialized_home(home: Path) -> tuple[object, str]:
    """Return `(tzinfo, canonical_name)` for an initialized home, or fail closed.

    `ENA.yaml` is the sole authority for the canonical timezone. Older schema-0.2
    homes may also carry a duplicate `SYSTEM.yaml canonical_timezone`; when that
    duplicate is known and disagrees, clock-dependent tools stop rather than
    silently choosing one side. If the legacy SYSTEM surface exists but cannot be
    parsed, the duplicate cannot be ruled out, so clock-dependent writes stop.
    """
    home = Path(home).expanduser().resolve()
    config = home / "ENA.yaml"
    if not config.is_file():
        raise EnaHomeError(f"ENA home is not initialized: missing {config}. {INIT_HINT}")

    data = read_control(config)
    validate_declared_home(home, data)
    name = scalar(data, "canonical_timezone")
    if missing(name):
        raise EnaHomeError(
            f"ENA home is not initialized: {config} has no canonical_timezone. {INIT_HINT}"
        )

    system = home / "SYSTEM.yaml"
    if system.is_file():
        system_data = read_control(system)
        system_name = scalar(system_data, "canonical_timezone")
        if not missing(system_name) and system_name != name:
            raise EnaHomeError(
                "canonical_timezone conflict: ENA.yaml is authoritative but SYSTEM.yaml "
                f"declares {system_name!r} while ENA.yaml declares {name!r}; reconcile the "
                "legacy duplicate before running a clock-dependent ENA tool"
            )

    try:
        return load_timezone(name), name
    except TimezoneUnavailable as exc:
        raise EnaHomeError(str(exc)) from exc


def home_of_package(package: Path) -> Path:
    """Return the initialized ENA home that owns a SAFE-CHANGE package.

    Package discovery no longer depends on a literal directory name `changes`.
    The nearest ancestor containing ENA.yaml owns the package only when the
    package is directly under that home's resolved `recovery.changes` path.
    """
    package = Path(package).expanduser().resolve()
    for candidate in package.parents:
        config = candidate / "ENA.yaml"
        if not config.is_file():
            continue
        changes = resolve_home_path(candidate, "recovery.changes", default_relative="changes")
        if package.parent != changes:
            raise EnaHomeError(
                f"{package} is not a SAFE-CHANGE package: its parent is {package.parent}, "
                f"but ENA.yaml recovery.changes resolves to {changes}. {PACKAGE_LAYOUT_HINT}"
            )
        return candidate.resolve()
    raise EnaHomeError(
        f"{package} is not a SAFE-CHANGE package because its ENA home is not initialized: "
        f"no ENA.yaml ancestor was found. {PACKAGE_LAYOUT_HINT}"
    )
