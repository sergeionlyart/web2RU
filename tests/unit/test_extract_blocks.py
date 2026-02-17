from __future__ import annotations

from lxml import html

from web2ru.extract.block_extractor import extract_blocks


def test_extract_blocks_skips_code_and_collects_text_nodes() -> None:
    root = html.fromstring(
        """
        <html><body><main>
          <p>Hello <strong>world</strong>.</p>
          <pre>do not translate</pre>
        </main></body></html>
        """
    )
    scope = root.xpath("//main")[0]
    blocks, _ = extract_blocks(
        scope,
        scope_mode="main",
        translation_unit="block",
        exclude_selectors=[],
    )
    assert blocks
    merged = " ".join(part.core for block in blocks for part in block.parts)
    assert "Hello" in merged
    assert "world" in merged
    assert "do not translate" not in merged
