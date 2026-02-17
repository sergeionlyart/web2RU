from __future__ import annotations

from web2ru.models import TranslationItem
from web2ru.translate.batcher import build_batches


def test_build_batches_keeps_small_sections_together() -> None:
    items = [
        TranslationItem(id="t_1", text="a" * 120, block_id="b1", section_hint="b1"),
        TranslationItem(id="t_2", text="b" * 120, block_id="b2", section_hint="b2"),
    ]
    batches = build_batches(
        items,
        max_chars=2000,
        max_items=20,
        prefer_section_boundary=True,
    )
    assert len(batches) == 1
    assert [item.id for item in batches[0].items] == ["t_1", "t_2"]


def test_build_batches_prefers_section_boundary_for_filled_batch() -> None:
    items = [
        TranslationItem(id="t_1", text="a" * 250, block_id="b1", section_hint="b1"),
        TranslationItem(id="t_2", text="a" * 250, block_id="b1", section_hint="b1"),
        TranslationItem(id="t_3", text="b" * 250, block_id="b2", section_hint="b2"),
        TranslationItem(id="t_4", text="b" * 250, block_id="b2", section_hint="b2"),
    ]

    with_boundary = build_batches(
        items,
        max_chars=1200,
        max_items=20,
        prefer_section_boundary=True,
    )
    without_boundary = build_batches(
        items,
        max_chars=1200,
        max_items=20,
        prefer_section_boundary=False,
    )

    assert len(with_boundary) == 2
    assert [item.id for item in with_boundary[0].items] == ["t_1", "t_2"]
    assert [item.id for item in with_boundary[1].items] == ["t_3", "t_4"]
    assert len(without_boundary) == 1
