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


def test_apply_blocks_replaces_code_comment_ranges_only() -> None:
    root = html.fromstring(
        "<html><body><pre><code># init\nx = 1\n# done\n</code></pre></body></html>"
    )
    code = root.xpath("//code")[0]
    original = code.text or ""
    first_start = original.find("init")
    first_end = first_start + len("init")
    second_start = original.find("done")
    second_end = second_start + len("done")
    xpath = root.getroottree().getpath(code)

    parts = [
        Part(
            id="t_000001",
            raw="init",
            lead_ws="",
            core="init",
            trail_ws="",
            node_ref=NodeRef(
                xpath=xpath,
                field="text",
                start_offset=first_start,
                end_offset=first_end,
            ),
            block_id="b_000001",
            translated_core="инициализация",
        ),
        Part(
            id="t_000002",
            raw="done",
            lead_ws="",
            core="done",
            trail_ws="",
            node_ref=NodeRef(
                xpath=xpath,
                field="text",
                start_offset=second_start,
                end_offset=second_end,
            ),
            block_id="b_000001",
            translated_core="готово",
        ),
    ]

    block = Block(block_id="b_000001", context="comments", parts=parts)
    applied = apply_blocks(root, [block])
    assert applied == 2
    assert root.xpath("string(//code)") == "# инициализация\nx = 1\n# готово\n"
