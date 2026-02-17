from __future__ import annotations

from lxml import html

from web2ru.extract.block_extractor import extract_blocks


def test_extract_blocks_skips_code_and_collects_text_nodes() -> None:
    root = html.fromstring(
        """
        <html><body><main>
          <p>Hello <strong>world</strong>.</p>
          <pre><code class="language-python">x = 1\nprint(x)</code></pre>
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
    assert "x = 1" not in merged
    assert "print(x)" not in merged


def test_extract_blocks_translates_markdown_pre_blocks() -> None:
    root = html.fromstring(
        """
        <html><body><main>
          <pre><code class="language-markdown"># ExecPlans
When writing complex features, use an ExecPlan.</code></pre>
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
    merged = " ".join(part.core for block in blocks for part in block.parts)
    assert "ExecPlans" in merged
    assert "use an ExecPlan" in merged


def test_extract_blocks_collects_only_comments_from_code_block() -> None:
    root = html.fromstring(
        """
        <html><body><main>
          <pre><code class="language-python"># initialize value
x = 1
print(x)
# done</code></pre>
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
    merged = " ".join(part.core for block in blocks for part in block.parts)
    assert "initialize value" in merged
    assert "done" in merged
    assert "x = 1" not in merged
    assert "print(x)" not in merged


def test_extract_blocks_detects_markdown_from_data_language_attr() -> None:
    root = html.fromstring(
        """
        <html><body><main>
          <pre data-language="md"><code># ExecPlans
When writing complex features, use an ExecPlan.</code></pre>
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
    merged = " ".join(part.core for block in blocks for part in block.parts)
    assert "ExecPlans" in merged
    assert "When writing complex features" in merged
