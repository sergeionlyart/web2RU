from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from web2ru.models import AttributeItem, Block, Part, TranslationItem
from web2ru.translate.batcher import build_batches
from web2ru.translate.cache_sqlite import TranslationCache
from web2ru.translate.client_openai import OpenAIClient
from web2ru.translate.token_protector import TOKEN_PROTECTOR_VERSION, protect_text, restore_text
from web2ru.translate.validate import ValidationOutcome, validate_translation_result

PROMPT_VERSION = "1.1"
GLOSSARY_VERSION = "1.1"
_MAX_CONTEXT_CHARS = 220
_MAX_GLOSSARY_TERMS = 40
_GLOSSARY_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9.+/#-]{2,}\b")
_SENTENCE_END_RE = re.compile(r"[.!?…](?:[\"')\\]]+)?\s*$")
_GLOSSARY_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "when",
    "where",
    "have",
    "has",
    "using",
    "used",
    "into",
    "without",
    "within",
    "across",
    "their",
    "there",
}
_STATIC_GLOSSARY: dict[str, str] = {
    "OpenAI": "OpenAI",
    "Codex": "Codex",
    "API": "API",
    "JSON": "JSON",
    "HTML": "HTML",
    "CSS": "CSS",
    "DOM": "DOM",
    "CLI": "CLI",
    "ExecPlan": "ExecPlan",
}


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
    batches_total: int = 0
    batch_chars_total: int = 0
    items_with_context: int = 0
    context_chars_total: int = 0
    glossary_terms: int = 0

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
        source_texts: list[str] = []
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
                source_texts.append(part.core)
                protected_inputs[part.id] = protected
                token_maps[part.id] = mapping
                id_to_part[part.id] = part
                items.append(
                    TranslationItem(
                        id=part.id,
                        text=protected,
                        block_id=part.block_id,
                        source_text=part.core,
                        section_hint=part.block_id,
                    )
                )

        for attr in attrs:
            protected, mapping = self._protect_if_needed(attr.text)
            attr.protected_text = protected
            attr.token_map = mapping
            self.stats.token_protected_count += len(mapping)
            source_texts.append(attr.text)
            protected_inputs[attr.id] = protected
            token_maps[attr.id] = mapping
            id_to_attr[attr.id] = attr
            items.append(
                TranslationItem(
                    id=attr.id,
                    text=protected,
                    hint=attr.hint,
                    allow_empty=False,
                    source_text=attr.text,
                    section_hint=f"attr:{attr.id}",
                )
            )

        if not items:
            return

        self._attach_local_context(items)
        document_glossary = self._build_document_glossary(source_texts)
        self.stats.glossary_terms = len(document_glossary)
        translated = self._translate_items_recursive(
            items=items,
            protected_inputs=protected_inputs,
            glossary=document_glossary,
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
        glossary: dict[str, str],
        depth: int,
    ) -> dict[str, str]:
        self.stats.split_depth_max = max(self.stats.split_depth_max, depth)
        result: dict[str, str] = {}
        for batch in build_batches(
            items,
            max_chars=self._batch_chars,
            max_items=self._max_items_per_batch,
            prefer_section_boundary=True,
        ):
            self.stats.batches_total += 1
            self.stats.batch_chars_total += batch.chars
            translated = self._translate_batch_with_retry(
                batch_items=batch.items,
                protected_inputs=protected_inputs,
                glossary=glossary,
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
                    glossary=glossary,
                    depth=depth + 1,
                )
                right = self._translate_items_recursive(
                    items=batch.items[mid:],
                    protected_inputs=protected_inputs,
                    glossary=glossary,
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
        glossary: dict[str, str],
    ) -> dict[str, str] | None:
        expected_ids = [item.id for item in batch_items]
        cache_key = self._make_cache_key(batch_items, glossary)
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
                "use_neighbor_context": True,
                "keep_style_consistent": True,
            },
            "items": [
                {
                    "id": item.id,
                    "text": item.text,
                    "hint": item.hint or "",
                    "context_prev": item.context_prev,
                    "context_next": item.context_next,
                    "section_hint": item.section_hint,
                }
                for item in batch_items
            ],
            "glossary": glossary,
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

    def _make_cache_key(self, items: list[TranslationItem], glossary: dict[str, str]) -> str:
        payload = json.dumps(
            [
                {
                    "id": item.id,
                    "text": item.text,
                    "hint": item.hint,
                    "context_prev": item.context_prev,
                    "context_next": item.context_next,
                    "section_hint": item.section_hint,
                }
                for item in items
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        glossary_payload = json.dumps(glossary, ensure_ascii=False, sort_keys=True)
        glossary_hash = hashlib.sha256(glossary_payload.encode("utf-8")).hexdigest()
        raw = "|".join(
            [
                self._model,
                self._reasoning_effort,
                PROMPT_VERSION,
                GLOSSARY_VERSION,
                TOKEN_PROTECTOR_VERSION,
                payload_hash,
                glossary_hash,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _attach_local_context(self, items: list[TranslationItem]) -> None:
        sections: dict[str, list[int]] = {}
        for idx, item in enumerate(items):
            key = item.section_hint or item.block_id or ""
            if not key:
                continue
            sections.setdefault(key, []).append(idx)

        for indices in sections.values():
            for pos, item_idx in enumerate(indices):
                item = items[item_idx]
                source_text = item.source_text or item.text
                if not self._should_include_neighbor_context(source_text):
                    item.context_prev = ""
                    item.context_next = ""
                    continue
                prev_text = ""
                if pos > 0:
                    previous = items[indices[pos - 1]]
                    prev_text = previous.source_text or ""
                next_text = ""
                if pos + 1 < len(indices):
                    following = items[indices[pos + 1]]
                    next_text = following.source_text or ""
                item.context_prev = self._normalize_context(prev_text)
                item.context_next = self._normalize_context(next_text)
                if item.context_prev or item.context_next:
                    self.stats.items_with_context += 1
                    self.stats.context_chars_total += len(item.context_prev) + len(
                        item.context_next
                    )

    def _should_include_neighbor_context(self, text: str) -> bool:
        compact = " ".join(text.split())
        if not compact:
            return False
        words = compact.split(" ")
        # Short fragments and headings are most sensitive to local context.
        if len(compact) <= 80 or len(words) <= 12:
            return True
        # For long text with a clear sentence ending, local context adds little quality but
        # significantly increases payload size.
        if _SENTENCE_END_RE.search(compact):
            return False
        # Mid-sentence fragments often start lowercase and benefit from neighboring context.
        return compact[0].islower()

    def _build_document_glossary(self, source_texts: list[str]) -> dict[str, str]:
        glossary = dict(_STATIC_GLOSSARY)
        counts: dict[str, int] = {}
        for text in source_texts:
            for match in _GLOSSARY_TOKEN_RE.finditer(text):
                token = match.group(0)
                if len(token) > 40:
                    continue
                lowered = token.lower()
                if lowered in _GLOSSARY_STOPWORDS:
                    continue
                if token.islower() and "-" not in token and not any(ch.isdigit() for ch in token):
                    continue
                counts[token] = counts.get(token, 0) + 1

        for token, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0])):
            if count < 2:
                continue
            if token in glossary:
                continue
            glossary[token] = token
            if len(glossary) >= _MAX_GLOSSARY_TERMS:
                break
        return glossary

    def _normalize_context(self, text: str) -> str:
        compact = " ".join(text.split())
        if len(compact) <= _MAX_CONTEXT_CHARS:
            return compact
        clipped = compact[: _MAX_CONTEXT_CHARS - 3].rstrip()
        return f"{clipped}..."
