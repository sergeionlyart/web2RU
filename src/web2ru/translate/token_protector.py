from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_PROTECTOR_VERSION = "1.1"
PLACEHOLDER_PREFIX = "WEB2RU_TP_"


_PROTECT_RE = re.compile(
    "|".join(
        [
            r"https?://[^\s)>'\"`]+",
            r"\bwww\.[^\s)>'\"`]+\b",
            r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b",
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
            r"\b(?:sha|md5|commit)?[=:]?[0-9a-fA-F]{7,64}\b",
            r"(?:^|\s)(?:--[a-zA-Z0-9][\w-]*|-[a-zA-Z])(?!\w)",
            r"\b\d+\.\d+\.\d+(?:[-+][\w.-]+)?\b",
            r"(?<!\w)(?:/[^\s]+|\./[^\s]+)(?!\w)",
            r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+\b",
            r"\b[a-z]+(?:[A-Z][a-z0-9]+){1,}[A-Za-z0-9]*\b",
        ]
    )
)

_PLACEHOLDER_RE = re.compile(rf"{PLACEHOLDER_PREFIX}\d{{6}}")


@dataclass(slots=True)
class ProtectedText:
    text: str
    mapping: dict[str, str]


def protect_text(value: str) -> ProtectedText:
    mapping: dict[str, str] = {}
    counter = 1

    def repl(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        placeholder = f"{PLACEHOLDER_PREFIX}{counter:06d}"
        mapping[placeholder] = token
        counter += 1
        return placeholder

    protected = _PROTECT_RE.sub(repl, value)
    return ProtectedText(text=protected, mapping=mapping)


def restore_text(value: str, mapping: dict[str, str]) -> str:
    restored = value
    for placeholder, token in mapping.items():
        restored = restored.replace(placeholder, token)
    return restored


def placeholders_in_text(value: str) -> list[str]:
    return _PLACEHOLDER_RE.findall(value)


def validate_placeholder_integrity(
    *,
    source_protected_text: str,
    translated_text: str,
    strict: bool,
) -> tuple[bool, str]:
    expected = placeholders_in_text(source_protected_text)
    got = placeholders_in_text(translated_text)
    if strict:
        if expected != got:
            return False, "placeholder_sequence_mismatch"
        return True, ""

    if sorted(expected) != sorted(got):
        return False, "placeholder_set_mismatch"
    return True, ""
