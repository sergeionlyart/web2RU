from __future__ import annotations

import json
from pathlib import Path

from web2ru.models import Block, NodeRef, Part
from web2ru.translate.client_openai import OpenAIResponsePayload
from web2ru.translate.translator import Translator


class _FakeClient:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def translate_payload(self, payload: dict[str, object]) -> OpenAIResponsePayload:
        self.payloads.append(payload)
        items = payload["items"]
        assert isinstance(items, list)
        translations = [{"id": item["id"], "text": item["text"]} for item in items]
        return OpenAIResponsePayload(
            raw_text=json.dumps({"translations": translations}, ensure_ascii=False),
            status="completed",
            incomplete_details=None,
            usage=None,
        )


def _part(part_id: str, text: str, block_id: str) -> Part:
    return Part(
        id=part_id,
        raw=text,
        lead_ws="",
        core=text,
        trail_ws="",
        node_ref=NodeRef(xpath="/html/body/main/p[1]", field="text"),
        block_id=block_id,
    )


def test_translator_sends_neighbor_context_and_glossary(tmp_path: Path) -> None:
    translator = Translator(
        api_key="test-key",
        model="gpt-5.1",
        reasoning_effort="none",
        max_output_tokens=2048,
        batch_chars=4000,
        max_items_per_batch=40,
        max_retries=1,
        allow_empty_parts=True,
        token_protect=False,
        token_protect_strict=False,
        use_cache=False,
        cache_db_path=str(tmp_path / "translation_cache.sqlite3"),
    )
    fake_client = _FakeClient()
    translator._client = fake_client  # type: ignore[assignment]

    block = Block(
        block_id="b_000001",
        context="",
        parts=[
            _part("t_000001", "The Translator uses OpenAI API.", "b_000001"),
            _part("t_000002", "This translator keeps glossary consistency.", "b_000001"),
            _part("t_000003", "OpenAI API responses should stay consistent.", "b_000001"),
        ],
    )

    translator.translate_blocks_and_attrs(blocks=[block], attrs=[])
    translator.close()

    assert len(fake_client.payloads) == 1
    payload = fake_client.payloads[0]
    items = payload["items"]
    assert isinstance(items, list)

    second = items[1]
    assert isinstance(second, dict)
    assert second["context_prev"] == "The Translator uses OpenAI API."
    assert second["context_next"] == "OpenAI API responses should stay consistent."

    glossary = payload["glossary"]
    assert isinstance(glossary, dict)
    assert glossary["OpenAI"] == "OpenAI"
    assert glossary["API"] == "API"
    assert translator.stats.items_with_context == 3
    assert translator.stats.glossary_terms >= 2


def test_translator_skips_context_for_long_complete_sentences(tmp_path: Path) -> None:
    translator = Translator(
        api_key="test-key",
        model="gpt-5.1",
        reasoning_effort="none",
        max_output_tokens=2048,
        batch_chars=4000,
        max_items_per_batch=40,
        max_retries=1,
        allow_empty_parts=True,
        token_protect=False,
        token_protect_strict=False,
        use_cache=False,
        cache_db_path=str(tmp_path / "translation_cache.sqlite3"),
    )
    fake_client = _FakeClient()
    translator._client = fake_client  # type: ignore[assignment]

    long_one = (
        "This sentence is intentionally long and complete so that it should not require "
        "neighbor context for a high quality translation output."
    )
    long_two = (
        "Another intentionally long and complete sentence follows here to validate that "
        "context payload is omitted when the fragment is self-contained."
    )
    block = Block(
        block_id="b_000002",
        context="",
        parts=[_part("t_000101", long_one, "b_000002"), _part("t_000102", long_two, "b_000002")],
    )

    translator.translate_blocks_and_attrs(blocks=[block], attrs=[])
    translator.close()

    payload = fake_client.payloads[0]
    items = payload["items"]
    assert isinstance(items, list)
    first = items[0]
    second = items[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first["context_prev"] == ""
    assert first["context_next"] == ""
    assert second["context_prev"] == ""
    assert second["context_next"] == ""
    assert translator.stats.items_with_context == 0
