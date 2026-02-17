from __future__ import annotations

import re

_LEAD_RE = re.compile(r"^\s*")
_TRAIL_RE = re.compile(r"\s*$")


def split_whitespace(raw: str) -> tuple[str, str, str]:
    lead = _LEAD_RE.match(raw).group(0)  # type: ignore[union-attr]
    trail = _TRAIL_RE.search(raw).group(0)  # type: ignore[union-attr]
    core = raw[len(lead) :]
    if trail:
        core = core[: len(core) - len(trail)]
    return lead, core, trail


def is_punctuation_or_ws(value: str) -> bool:
    return bool(value) and all(ch.isspace() or not ch.isalnum() for ch in value)
