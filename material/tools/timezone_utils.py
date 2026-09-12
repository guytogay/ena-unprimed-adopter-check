#!/usr/bin/env python3
"""Small timezone helper for ENA reference tools.

Uses the standard library first. UTC works without an external tz database;
other IANA zones require system zoneinfo data or the optional `tzdata` package.
"""

from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimezoneUnavailable(ValueError):
    pass


def load_timezone(name: str):
    if name == "REPLACE_WITH_CONFIRMED_IANA_TIMEZONE":
        raise TimezoneUnavailable(
            "canonical_timezone still contains the shipped example placeholder "
            "REPLACE_WITH_CONFIRMED_IANA_TIMEZONE; replace it with the confirmed IANA timezone before use"
        )
    if name in {"UTC", "Etc/UTC"}:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise TimezoneUnavailable(
            f"IANA timezone {name!r} is unavailable on this Python installation. "
            "Install the `tzdata` package (for example: python -m pip install tzdata) "
            "or provide another confirmed IANA timezone available to the Host."
        ) from exc
