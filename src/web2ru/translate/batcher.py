from __future__ import annotations

from web2ru.models import TranslateBatch, TranslationItem


def _section_key(item: TranslationItem) -> str:
    if item.block_id:
        return f"block:{item.block_id}"
    if item.section_hint:
        return f"section:{item.section_hint}"
    return ""


def build_batches(
    items: list[TranslationItem],
    *,
    max_chars: int,
    max_items: int,
    prefer_section_boundary: bool = False,
) -> list[TranslateBatch]:
    batches: list[TranslateBatch] = []
    current: list[TranslationItem] = []
    char_count = 0

    for item in items:
        item_len = len(item.text)
        flush_for_size = current and (
            len(current) + 1 > max_items or char_count + item_len > max_chars
        )
        flush_for_section = False
        if prefer_section_boundary and current:
            next_key = _section_key(item)
            current_key = _section_key(current[-1])
            if next_key and current_key and next_key != current_key:
                # Keep nearby context together unless current batch is tiny.
                flush_for_section = char_count >= max(400, max_chars // 3) or len(current) >= max(
                    6, max_items // 3
                )
        if flush_for_size or flush_for_section:
            batches.append(TranslateBatch(items=current, chars=char_count))
            current = []
            char_count = 0
        current.append(item)
        char_count += item_len

    if current:
        batches.append(TranslateBatch(items=current, chars=char_count))
    return batches
