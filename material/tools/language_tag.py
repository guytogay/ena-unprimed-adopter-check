#!/usr/bin/env python3
"""Small structural validator for configured working-language tags.

This deliberately checks only BCP-47-like syntax. It does not claim registry
membership and it cannot prove that a user/operator actually confirmed a tag.
"""

from __future__ import annotations

import re


# A bounded structural check is enough for ENA's control surface: a normal
# language subtag plus hyphen-separated alphanumeric subtags, or private-use /
# grandfathered-style x-/i- forms. Registry membership remains out of scope.
_TAG = re.compile(
    r"^(?:"
    r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*"
    r"|[xX](?:-[A-Za-z0-9]{1,8})+"
    r"|[iI](?:-[A-Za-z0-9]{1,8})+"
    r")$"
)

# These are ENA control-state words, not working-language declarations, even
# though some happen to look like alphabetic subtags.
_RESERVED = {
    "UNKNOWN",
    "UNAVAILABLE",
    "NOT_NEEDED",
    "NOT_APPLICABLE",
    "DEFERRED",
    "STALLED_UNKNOWN",
}


def language_tag_problem(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return "language tag is empty or not a string"
    if value != value.strip():
        return "language tag has leading or trailing whitespace"
    tag = value
    if len(tag) > 255:
        return "language tag is longer than 255 characters"
    if tag.upper() in _RESERVED:
        return f"{tag!r} is an ENA control-state token, not a confirmed language tag"
    if not _TAG.fullmatch(tag):
        return (
            f"{tag!r} is not a supported BCP-47-like language-tag shape; "
            "use hyphen-separated subtags such as en, en-US, or zh-Hans-CN"
        )
    return None


def require_language_tag(value: object) -> str:
    problem = language_tag_problem(value)
    if problem:
        raise ValueError(problem)
    return str(value)
