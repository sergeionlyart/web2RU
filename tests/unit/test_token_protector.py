from __future__ import annotations

from web2ru.translate.token_protector import (
    placeholders_in_text,
    protect_text,
    restore_text,
    validate_placeholder_integrity,
)


def test_token_protector_roundtrip() -> None:
    src = "Use https://example.com and --flag in snake_case id user_name."
    protected = protect_text(src)
    assert protected.text != src
    assert len(protected.mapping) >= 2

    restored = restore_text(protected.text, protected.mapping)
    assert restored == src


def test_token_integrity_strict() -> None:
    src = "See WEB2RU_TP_000001 and WEB2RU_TP_000002"
    ok, err = validate_placeholder_integrity(
        source_protected_text=src,
        translated_text="WEB2RU_TP_000002 WEB2RU_TP_000001",
        strict=True,
    )
    assert not ok
    assert err == "placeholder_sequence_mismatch"


def test_placeholders_find() -> None:
    found = placeholders_in_text("A WEB2RU_TP_000010 B WEB2RU_TP_000011")
    assert found == ["WEB2RU_TP_000010", "WEB2RU_TP_000011"]
