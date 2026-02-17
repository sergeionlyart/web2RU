from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from web2ru.models import AttributeItem, Block, Part, TranslationItem
from web2ru.translate.batcher import build_batches
from web2ru.translate.cache_sqlite import TranslationCache
from web2ru.translate.client_openai import OpenAIClient
from web2ru.translate.token_protector import TOKEN_PROTECTOR_VERSION, protect_text, restore_text
from web2ru.translate.validate import ValidationOutcome, validate_translation_result

PROMPT_VERSION = "1.0"
GLOSSARY_VERSION = "1.0"


@dataclass(slots=True)
class TranslateStats:
    requests: int = 0
    retries: int = 0
    split_depth_max: int = 0
    cache_hits: int = 0
    failures: list[dict[str, str]] = None  # type: ignore[assignment]
    fallback_parts: int = 0
    translated_parts: int = 0
    translated_attrs: int = 0
    token_protected_count: int = 0

    def __post_init__(self) -> None:
        if self.failures is None:
            self.failures = []


class Translator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int,
        batch_chars: int,
        max_items_per_batch: int,
        max_retries: int,
        allow_empty_parts: bool,
        token_protect: bool,
        token_protect_strict: bool,
        use_cache: bool,
        cache_db_path: str,
    ) -> None:
        self._client = OpenAIClient(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
        )
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._batch_chars = batch_chars
        self._max_items_per_batch = max_items_per_batch
        self._max_retries = max_retries
        self._allow_empty_parts = allow_empty_parts
        self._token_protect = token_protect
        self._token_protect_strict = token_protect_strict
        self._cache = TranslationCache(db_path=Path(cache_db_path)) if use_cache else None
        self.stats = TranslateStats()

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()

    def translate_blocks_and_attrs(
        self,
        *,
        blocks: list[Block],
        attrs: list[AttributeItem],
    ) -> None:
        items: list[TranslationItem] = []
        protected_inputs: dict[str, str] = {}
        token_maps: dict[str, dict[str, str]] = {}
        id_to_part: dict[str, Part] = {}
        id_to_attr: dict[str, AttributeItem] = {}

        for block in blocks:
            for part in block.parts:
                protected, mapping = self._protect_if_needed(part.core)
                part.protected_core = protected
                part.token_map = mapping
                self.stats.token_protected_count += len(mapping)
                protected_inputs[part.id] = protected
                token_maps[part.id] = mapping
                id_to_part[part.id] = part
                items.append(
                    TranslationItem(
                        id=part.id,
                        text=protected,
                        block_id=part.block_id,
                    )
                )

        for attr in attrs:
            protected, mapping = self._protect_if_needed(attr.text)
            attr.protected_text = protected
            attr.token_map = mapping
            self.stats.token_protected_count += len(mapping)
            protected_inputs[attr.id] = protected
            token_maps[attr.id] = mapping
            id_to_attr[attr.id] = attr
            items.append(
                TranslationItem(
                    id=attr.id,
                    text=protected,
                    hint=attr.hint,
                    allow_empty=False,
                )
            )

        if not items:
            return

        translated = self._translate_items_recursive(
            items=items,
            protected_inputs=protected_inputs,
            depth=0,
        )

        for item_id, translated_text in translated.items():
            restored = restore_text(translated_text, token_maps[item_id])
            if item_id in id_to_part:
                id_to_part[item_id].translated_core = restored
                self.stats.translated_parts += 1
            elif item_id in id_to_attr:
                id_to_attr[item_id].translated_text = restored
                self.stats.translated_attrs += 1

    def _protect_if_needed(self, text: str) -> tuple[str, dict[str, str]]:
        if not self._token_protect:
            return text, {}
        protected = protect_text(text)
        return protected.text, protected.mapping

    def _translate_items_recursive(
        self,
        *,
        items: list[TranslationItem],
        protected_inputs: dict[str, str],
        depth: int,
    ) -> dict[str, str]:
        self.stats.split_depth_max = max(self.stats.split_depth_max, depth)
        result: dict[str, str] = {}
        for batch in build_batches(
            items,
            max_chars=self._batch_chars,
            max_items=self._max_items_per_batch,
        ):
            translated = self._translate_batch_with_retry(
                batch_items=batch.items,
                protected_inputs=protected_inputs,
            )
            if translated is None:
                if len(batch.items) <= 1:
                    item = batch.items[0]
                    result[item.id] = item.text
                    self.stats.fallback_parts += 1
                    self.stats.failures.append(
                        {"id": item.id, "reason": "fallback_original_after_retries"}
                    )
                    continue
                mid = len(batch.items) // 2
                left = self._translate_items_recursive(
                    items=batch.items[:mid],
                    protected_inputs=protected_inputs,
                    depth=depth + 1,
                )
                right = self._translate_items_recursive(
                    items=batch.items[mid:],
                    protected_inputs=protected_inputs,
                    depth=depth + 1,
                )
                result.update(left)
                result.update(right)
                continue
            result.update(translated)
        return result

    def _translate_batch_with_retry(
        self,
        *,
        batch_items: list[TranslationItem],
        protected_inputs: dict[str, str],
    ) -> dict[str, str] | None:
        expected_ids = [item.id for item in batch_items]
        cache_key = self._make_cache_key(batch_items)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self.stats.cache_hits += 1
                return cached.translations

        payload = {
            "task": "translate_items",
            "target_language": "ru",
            "rules": {
                "keep_placeholders": True,
                "no_html": True,
                "allow_empty_parts": self._allow_empty_parts,
            },
            "items": [
                {"id": item.id, "text": item.text, "hint": item.hint or ""} for item in batch_items
            ],
            "glossary": {"OpenAI": "OpenAI", "Codex": "Codex"},
        }

        last_error = ""
        for _ in range(self._max_retries):
            self.stats.requests += 1
            try:
                response = self._client.translate_payload(payload)
            except Exception as exc:  # noqa: BLE001
                self.stats.retries += 1
                last_error = f"request_error:{type(exc).__name__}"
                continue

            if response.status == "incomplete" or response.incomplete_details:
                self.stats.retries += 1
                last_error = "incomplete_response"
                continue

            outcome: ValidationOutcome = validate_translation_result(
                raw_text=response.raw_text,
                expected_ids=expected_ids,
                protected_inputs={k: protected_inputs[k] for k in expected_ids},
                strict_placeholders=self._token_protect_strict,
                allow_empty_parts=self._allow_empty_parts,
            )
            if outcome.ok and outcome.translations is not None:
                if self._cache is not None:
                    self._cache.put(cache_key, outcome.translations)
                return outcome.translations

            self.stats.retries += 1
            last_error = outcome.error

        self.stats.failures.append(
            {"id": ",".join(expected_ids[:3]), "reason": f"batch_failed:{last_error}"}
        )
        return None

    def _make_cache_key(self, items: list[TranslationItem]) -> str:
        payload = json.dumps(
            [{"id": item.id, "text": item.text, "hint": item.hint} for item in items],
            ensure_ascii=False,
            sort_keys=True,
        )
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        raw = "|".join(
            [
                self._model,
                self._reasoning_effort,
                PROMPT_VERSION,
                GLOSSARY_VERSION,
                TOKEN_PROTECTOR_VERSION,
                payload_hash,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
