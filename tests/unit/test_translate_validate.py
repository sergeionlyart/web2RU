from __future__ import annotations

from web2ru.translate.validate import validate_translation_result


def test_validate_allows_markdown_heading_if_source_has_heading() -> None:
    outcome = validate_translation_result(
        raw_text='{"translations":[{"id":"t_000001","text":"# Планы выполнения"}]}',
        expected_ids=["t_000001"],
        protected_inputs={"t_000001": "# ExecPlans"},
        strict_placeholders=False,
        allow_empty_parts=True,
    )
    assert outcome.ok


def test_validate_rejects_injected_markdown_heading() -> None:
    outcome = validate_translation_result(
        raw_text='{"translations":[{"id":"t_000001","text":"# Планы выполнения"}]}',
        expected_ids=["t_000001"],
        protected_inputs={"t_000001": "ExecPlans"},
        strict_placeholders=False,
        allow_empty_parts=True,
    )
    assert not outcome.ok
    assert outcome.error == "html_markdown_detected"
