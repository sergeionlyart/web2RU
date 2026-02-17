from __future__ import annotations

from lxml import html

from web2ru.apply.apply_blocks import apply_blocks
from web2ru.models import Block, NodeRef, Part


def test_apply_blocks_replaces_text_without_structure_change() -> None:
    root = html.fromstring("<html><body><p>Hello <strong>world</strong>.</p></body></html>")
    strong = root.xpath("//strong")[0]
    assert strong.text == "world"
    xpath = root.getroottree().getpath(strong)
    part = Part(
        id="t_000001",
        raw="world",
        lead_ws="",
        core="world",
        trail_ws="",
        node_ref=NodeRef(xpath=xpath, field="text"),
        block_id="b_000001",
        translated_core="мир",
    )
    block = Block(block_id="b_000001", context="world", parts=[part])
    applied = apply_blocks(root, [block])
    assert applied == 1
    assert root.xpath("string(//strong)") == "мир"
    assert len(root.xpath("//strong")) == 1
