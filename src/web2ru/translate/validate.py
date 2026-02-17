from __future__ import annotations

import json
import re
from dataclasses import dataclass

from jsonschema import ValidationError, validate

from web2ru.translate.schema import TRANSLATIONS_SCHEMA
from web2ru.translate.token_protector import validate_placeholder_integrity

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_FENCE_RE = re.compile(r"```")
_MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s", re.MULTILINE)


@dataclass(slots=True)
class ValidationOutcome:
    ok: bool
    error: str = ""
    translations: dict[str, str] | None = None


def parse_response_json(raw_text: str) -> ValidationOutcome:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return ValidationOutcome(ok=False, error="json_parse_error")

    try:
        validate(payload, TRANSLATIONS_SCHEMA)
    except ValidationError:
        return ValidationOutcome(ok=False, error="schema_error")

    out = {entry["id"]: entry["text"] for entry in payload["translations"]}
    return ValidationOutcome(ok=True, translations=out)


def validate_translation_result(
    *,
    raw_text: str,
    expected_ids: list[str],
    protected_inputs: dict[str, str],
    strict_placeholders: bool,
    allow_empty_parts: bool,
) -> ValidationOutcome:
    parsed = parse_response_json(raw_text)
    if not parsed.ok or parsed.translations is None:
        return parsed

    translated_map = parsed.translations
    if sorted(translated_map.keys()) != sorted(expected_ids):
        return ValidationOutcome(ok=False, error="id_coverage_error")

    # Keep order stable (model must return same order as input IDs).
    returned_order = list(translated_map.keys())
    if returned_order != expected_ids:
        return ValidationOutcome(ok=False, error="id_order_error")

    for item_id, translated in translated_map.items():
        source = protected_inputs[item_id]
        if _HTML_TAG_RE.search(translated) and not _HTML_TAG_RE.search(source):
            return ValidationOutcome(ok=False, error="html_markdown_detected")
        if _MD_FENCE_RE.search(translated) and not _MD_FENCE_RE.search(source):
            return ValidationOutcome(ok=False, error="html_markdown_detected")
        if _MD_HEADING_RE.search(translated) and not _MD_HEADING_RE.search(source):
            return ValidationOutcome(ok=False, error="html_markdown_detected")
        ok, err = validate_placeholder_integrity(
            source_protected_text=source,
            translated_text=translated,
            strict=strict_placeholders,
        )
        if not ok:
            return ValidationOutcome(ok=False, error=f"token_integrity:{err}")
        if not allow_empty_parts and source.strip() and not translated.strip():
            return ValidationOutcome(ok=False, error="empty_part_disallowed")

    return ValidationOutcome(ok=True, translations=translated_map)
