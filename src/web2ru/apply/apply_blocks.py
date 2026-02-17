from __future__ import annotations

from lxml import etree

from web2ru.models import Block


def apply_blocks(root: etree._Element, blocks: list[Block]) -> int:
    applied = 0
    for block in blocks:
        for part in block.parts:
            translated = part.translated_core if part.translated_core is not None else part.core
            new_text = f"{part.lead_ws}{translated}{part.trail_ws}"
            nodes = root.xpath(part.node_ref.xpath)
            if not nodes:
                continue
            node = nodes[0]
            if not isinstance(node, etree._Element):
                continue
            if part.node_ref.field == "text":
                node.text = new_text
                applied += 1
            elif part.node_ref.field == "tail":
                node.tail = new_text
                applied += 1
    return applied
