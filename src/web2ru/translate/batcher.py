from __future__ import annotations

from web2ru.models import TranslateBatch, TranslationItem


def build_batches(
    items: list[TranslationItem],
    *,
    max_chars: int,
    max_items: int,
) -> list[TranslateBatch]:
    batches: list[TranslateBatch] = []
    current: list[TranslationItem] = []
    char_count = 0

    for item in items:
        item_len = len(item.text)
        can_fit = current and (len(current) + 1 > max_items or char_count + item_len > max_chars)
        if can_fit:
            batches.append(TranslateBatch(items=current, chars=char_count))
            current = []
            char_count = 0
        current.append(item)
        char_count += item_len

    if current:
        batches.append(TranslateBatch(items=current, chars=char_count))
    return batches
